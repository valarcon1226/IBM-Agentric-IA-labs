# Decisiones para construir `02-business-registry-enricher`

Escritas por Claude **antes** de la ejecución. Mandan sobre el README y el EXECUTION_PLAN cuando
los contradigan. Si algo no está aquí y bloquea, detente y repórtalo; si no bloquea, elige lo más
simple, anótalo en el reporte y sigue. Regla general: la solución más simple que funcione,
reutilizando patrones de `01-smart-data-intake`; nunca recortes validación, manejo de errores ni
seguridad.

## E1 — Estructura y versiones

- Estructura del README §8 (sin carpeta `backend/`): `app/`, `tests/`, `Dockerfile`,
  `docker-compose.yml`, `init-db.sql`, `requirements.txt`, `requirements-dev.txt`,
  `pyproject.toml`, `.env.example`, `.gitignore` (copia el de `01-smart-data-intake/backend`).
  Agrega solo `app/config.py` y `app/security.py`. `n8n/workflows/` cuando llegue E10.
- Python 3.12, `.venv` en la raíz del proyecto. Herramientas de dev (pytest, ruff, mypy) con las
  mismas versiones que `01-smart-data-intake/backend/requirements-dev.txt`. Librerías nuevas
  (`zeep`, `aiolimiter`, `tenacity`, `httpx`, `asyncpg`): versión fija de PyPI, anotada en el
  reporte.
- Puertos del host (8000, 5432 y 5678 ya están en uso por otros proyectos): `enricher_api`
  `8002:8000`, `postgres` `5434:5432`, `n8n` `5679:5678`. Actualiza los `curl` del README.
- Healthchecks en los 3 servicios (patrón de 01: `pg_isready`, `urllib` a `/health`, `wget` a
  `/healthz`). `enricher_api` depende de `postgres` healthy.

## E2 — Configuración, secretos y autenticación (igual que 01)

- `config.py` con pydantic-settings. Requeridas sin defecto: `DATABASE_URL`, `API_KEY`,
  `CH_API_KEY`, `INSEE_API_KEY`. `.env.example` con `change_me_<nombre>`; `.env` ignorado.
- Bearer `API_KEY` en todas las rutas menos `/health` (copia `security.py` de 01). Agrega
  `-H "Authorization: Bearer $API_KEY"` a los `curl` del README.

## E3 — Base de datos

- `init-db.sql` con las dos tablas del README §4, montado en el init de postgres.
- SQLAlchemy 2 **async** con `asyncpg` (los conectores son async; no bloquear el event loop).
  SQL plano con `text()` y parámetros, como en 01. Engine cacheado (`functools.cache`).

## E4 — Enrutado por país y validación de entrada

- `GB` → Companies House (`identifier` = company number, `^[A-Z0-9]{8}$` tras `upper()`).
- `FR` → INSEE (`identifier` = SIREN, `^\d{9}$`).
- Cualquier otro código de estado miembro de la UE (lista fija de los 27 códigos VIES, `EL` para
  Grecia) → VIES (`identifier` = número de IVA sin prefijo de país, `^[A-Z0-9]{2,12}$`).
- País o identificador inválido → 422 (validación Pydantic), nunca una llamada al registro.
- Lote: máximo 100 empresas por request (422 si se excede); se deduplican por (país, id).

## E5 — Conectores

- **Companies House:** `GET https://api.company-information.service.gov.uk/company/{number}` con
  Basic Auth (`CH_API_KEY` como usuario, contraseña vacía). `httpx.AsyncClient`.
  `aiolimiter.AsyncLimiter(600, 300)` a nivel de módulo.
- **INSEE:** el portal antiguo con bearer token fue reemplazado; usa la API Sirene 3.11:
  `GET https://api.insee.fr/api-sirene/3.11/siren/{siren}` con header
  `X-INSEE-Api-Key-Integration: <INSEE_API_KEY>`. Renombra `INSEE_BEARER_TOKEN` → `INSEE_API_KEY`
  en el README. Si la documentación oficial actual dice otra cosa, sigue la documentación y
  anótalo. `AsyncLimiter(30, 60)`.
- **VIES:** `zeep` con el WSDL oficial `checkVatService`. Zeep es síncrono: llámalo con
  `asyncio.to_thread`. Sin limiter (VIES no publica cuota), con tenacity.
- **Reintentos:** tenacity, exponencial, hasta 5 intentos, solo en 429, 5xx y errores de red.
  404 no se reintenta. En tests, espera cero (parametriza el `wait`).
- **Normalización** a la forma del README §5: `company_name`, `status` en minúsculas
  (CH: `company_status` tal cual; INSEE: `A`→`active`, `C`→`ceased`; VIES: `valid`/`invalid`),
  `incorporation_date` (CH `date_of_creation`, INSEE `dateCreationUniteLegale`, VIES `null`),
  `raw_data` con la respuesta original.
- **`api_logs`:** cada llamada a un registro (éxito o error) inserta registry_name, endpoint (sin
  credenciales), response_code, response_time_ms, error_message, company_identifier. Un fallo al
  escribir el log se registra con `logging` y no tumba la petición.

## E6 — Tests sin llamadas en vivo

- El DoD exige que CI no llame a registros reales. Por eso **VIES también se testea con mocks**
  (respuesta de zeep simulada), no contra los números de prueba de la Comisión. Un test opcional
  contra el servicio de prueba de VIES (`checkVatTestService`, número `100` válido) va marcado
  `live` y excluido por defecto (`addopts`).
- CH e INSEE: `httpx.MockTransport`.
- **Limiter:** no esperes 5 minutos. Tras 600 `acquire()` sobre un `AsyncLimiter(600, 300)`,
  verifica que `has_capacity()` es `False` y que un `acquire()` extra no termina dentro de un
  `asyncio.wait_for` corto (timeout). Igual para INSEE con 30.

## E7 — Caché

- Lectura: `... WHERE country_code=:c AND company_identifier=:i AND last_updated > NOW() -
  INTERVAL '30 days'`. Miss → registro → `INSERT ... ON CONFLICT (country_code,
  company_identifier) DO UPDATE ... last_updated = NOW()`.
- Solo se cachean consultas exitosas (incluido VIES `invalid`, que es una respuesta válida). Los
  errores y los "no encontrado" no se cachean.
- Test: fila de 31 días → llama al registro; fila fresca → no llama.

## E8 — Endpoints

- `POST /api/v1/enrich`: respuesta del README §5. Un fallo en una empresa no tumba el lote: ese
  resultado lleva `status: "error"` o `"not_found"`, `company_name: null`, y un campo opcional
  `error` con un mensaje corto sin detalles internos.
- `GET /api/v1/enrich/{country}/{identifier}?force_refresh=false`: 404 si no existe, 502 si el
  registro falla tras los reintentos. `force_refresh=true` salta la lectura de caché pero sí
  actualiza la caché.
- `GET /health`: 200 si Postgres responde, 503 si no (patrón de 01).

## E9 — Integración y E2E

- Tests `integration`/`e2e` contra el stack real de compose (API en `localhost:8002`), con skip
  limpio si no está arriba, excluidos por defecto (patrón de 01 `test_integration_e2e.py`).
- El E2E **no** llama a registros reales: inserta una fila fresca en `company_cache` y verifica
  `cached: true`, luego la borra. El flujo `cached: false` se cubre con tests de la app con
  conectores mockeados.

## E10 — n8n

- Servicio `n8n` en compose y workflow exportado en `n8n/workflows/enrich.json` con los nodos del
  README §9 (Webhook → HTTP Request → Set → Google Sheets). Credenciales (Header Auth con la API
  key, Google OAuth2) se configuran en n8n después de importar; nada de secretos en el JSON. La
  escritura real en Google Sheets la valida la usuaria.

## E11 — Qué no hacer

- No agregues Redis, Celery, Alembic, ni un job de expiración de caché.
- No hagas commit ni push. No toques archivos `.env`.
- Cada lote termina con un reporte en `docs/reviews/T-02-<lote>.md` con la salida real de cada
  comando; si algo falla o queda bloqueado, dilo tal cual en vez de marcarlo hecho.
