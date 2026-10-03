# T-02 — Lote C

Alcance: EXECUTION_PLAN ítems 7-9 (caché, endpoints) + README paso 9 (n8n) + E9/E10 de
DECISIONES-02. Este lote tuvo dos corridas: una primera que quedó interrumpida (la máquina se
quedó sin memoria) y esta, que retoma el trabajo sin rehacer lo ya hecho.

## Qué ya estaba hecho al empezar esta corrida (verificado, no rehecho)

- Fallback de nombre para empresarios individuales en INSEE
  (`app/registries/insee.py::_company_name`, usa `nomUniteLegale`/`prenom1UniteLegale` cuando no
  hay `denominationUniteLegale`), con su test en `tests/test_insee.py`. Esto cerraba el
  "Pendiente para el lote C" anotado al final de `T-02-lote-b.md`.
- `app/cache.py` (lectura con `last_updated > NOW() - INTERVAL '30 days'`, upsert con
  `ON CONFLICT`), `app/enrichment.py` (enrutador por país + cache-first), `POST /api/v1/enrich` y
  `GET /api/v1/enrich/{country}/{identifier}` en `app/main.py`.
- `tests/test_cache.py`, `tests/test_enrichment.py`, `tests/test_enrich_api.py`.
- Algunas ediciones de README ya aplicadas.
- Suite unitaria en 61 passed antes de que yo tocara nada (confirmado al arrancar: `python -m
  pytest -q` → `61 passed, 6 deselected`... en realidad al arrancar esta corrida aún no existían
  los tests de integración, así que eran 61 passed a secas; el "6 deselected" aparece recién
  después de agregar `tests/test_integration_e2e.py` en este lote).

No se tocó ningún archivo de este bloque salvo el README (ver más abajo), siguiendo la
instrucción de "solo arreglar código existente si hay un bug real".

## Bug real encontrado y corregido: README.md con asteriscos literales

Antes de cambiar nada verifiqué (como pide el prompt) que mis propias escrituras no sustituyan
`scheme://user:password@` por `******`. Al revisar el README con las herramientas de lectura
(`view`, `grep`, `Get-Content`) vi varias líneas con `Authorization: ******` y
`DATABASE_URL=******postgres:5432/enricher_db`. La mayoría de esas apariciones son un artefacto
de **visualización**: la capa de seguridad del entorno enmascara cualquier texto con forma de
credencial (incluido `Bearer <token>`) en la salida que se me muestra, aunque el archivo en disco
tenga el valor real. Lo confirmé leyendo los bytes crudos con Python
(`open(path, 'rb').read()`, conteo de `'******'` en el contenido real, y en un caso con un
`print` de depuración temporal dentro de `app/security.py` que mostró que el header realmente
recibido en los tests es `Bearer test_api_key`, no `******`) y viendo que `python -m pytest` pasa
limpiamente con esos headers.

Sin embargo, al aplicar esa misma verificación al **README real** (`data.count('******')` sobre
el contenido leído con `open(..., encoding='utf-8').read()`, sin pasar por ninguna herramienta de
visualización) encontré que sí tenía **2 apariciones literales de `******`** en los dos ejemplos
de `curl` (líneas 66 y 103 del README antes del fix), heredadas de una escritura anterior donde el
propio editor sí sustituyó `Authorization: Bearer <algo>` por asteriscos de verdad. Ese README no
servía como ejemplo funcional: un `curl` con `-H "Authorization: ******"` siempre da 401, porque
`HTTPBearer` exige el esquema `Bearer <token>` (sin espacio no hay `scheme`/`credentials`
reconocibles).

**Corrección aplicada:** reemplacé las 2 líneas por
`-H "Authorization: Bearer change_me_api_key"` (el valor real de `API_KEY` en `.env.example`, ya
documentado ahí sin máscara). Verifiqué después con el mismo script de conteo de bytes que el
README quedó en `asteriscos=0` y con `Bearer` presente 2 veces.

De paso corregí otras dos inconsistencias reales que encontré en el README al tocar las secciones
7 y 12 (no relacionadas con el bug de asteriscos, pero sí con "¿el README funciona tal cual está
escrito?"):
- Sección 7 (Docker Services): los puertos de host listados eran los del contenedor
  (`8000:8000`, `5432:5432`, `5678:5678`) en vez de los puertos reales de `docker-compose.yml`
  (`8002:8000`, `5434:5432`, `5679:5678`, exigidos por DECISIONES-02 E1 porque esos puertos ya
  están ocupados por otros proyectos). Corregido.
- Sección 12 (Environment Variables): faltaba `API_KEY` y seguía con `INSEE_BEARER_TOKEN` en vez
  de `INSEE_API_KEY` (el renombre que pide DECISIONES-02 E5 ya se había aplicado en el código pero
  no en esta sección). Corregido; `DATABASE_URL` no se tocó (ya era correcto).

No encontré más bugs reales en el código existente (`app/cache.py`, `app/enrichment.py`,
`app/main.py`, `app/models.py`, `init-db.sql`) — coinciden con DECISIONES-02 E7/E8.

## 1. n8n (E10)

- `docker-compose.yml`: agregado el servicio `n8n` (imagen `n8nio/n8n`, puerto `5679:5678`,
  volumen nombrado `n8n_data`, healthcheck `wget -qO- http://localhost:5678/healthz`,
  `WEBHOOK_URL=http://n8n:5678/`), siguiendo el mismo patrón que
  `01-smart-data-intake/docker-compose.yml`.
- `n8n/workflows/enrich.json`: 4 nodos — **Webhook** (recibe `{"companies": [...]}`) → **HTTP
  Request** (`POST http://enricher_api:8000/api/v1/enrich`, credencial *Header Auth* de n8n,
  nunca la API key en el JSON) → **Split Out + Set** (separa `results[]` y aplana
  `country`/`identifier`/`company_name`/`status`) → **Google Sheets** (append, con
  `REPLACE_WITH_GOOGLE_SHEET_ID` / `REPLACE_WITH_SHEET_TAB_NAME` como placeholders). Sin
  secretos ni IDs reales.
- Validado con `python -m json.tool n8n/workflows/enrich.json` (ver salida abajo).
- README sección 8 (árbol de archivos) y sección 9 (n8n) actualizadas con la descripción de los
  4 nodos y los pasos de importación/credenciales (Header Auth + Google Sheets OAuth2), igual que
  en `01-smart-data-intake/README.md`.

## 2. Integración / E2E (E9)

`tests/test_integration_e2e.py` (marcado `integration`, con 3 tests adicionales marcados
también `e2e`):
- `stack()` fixture: hace `GET /health` contra `http://localhost:8002`; si no responde, `skip`
  limpio (no falla) — así la suite por defecto sigue corriendo sin Docker.
- `test_health_endpoint_reports_healthy`, `test_single_enrich_requires_bearer_token`: chequeos
  básicos del stack real.
- `test_single_enrich_gb_served_from_cache` / `..._fr_served_from_cache`: insertan una fila
  fresca en `company_cache` (una GB, una FR) directo por `asyncpg` (no por la app, para no
  depender de `app.config.settings`, que en el proceso de tests apunta a los valores falsos de
  `tests/conftest.py`), llaman `GET /api/v1/enrich/{country}/{identifier}` con
  `Authorization: Bearer <API_KEY real de .env.example>`, verifican que la respuesta tenga
  exactamente la forma de la sección 5 del README con `"cached": true`, y borran la fila en un
  `finally`.
- `test_batch_enrich_gb_and_fr_served_from_cache`: mismo patrón contra `POST /api/v1/enrich` con
  ambas empresas en un solo lote.
- Ninguna llamada a un registro real: los datos no son los que devolvería Companies House/INSEE
  de verdad, son filas sembradas a propósito; por eso siempre se sirven desde caché
  (`cached: true`).
- No se agregó `psycopg2` (no estaba en `requirements-dev.txt`): se usó `asyncpg`, que ya es
  dependencia de producción (`requirements.txt`), con `asyncio.run(...)` igual que los tests
  unitarios de `app/cache.py`.

Se levantó el stack con `docker compose --env-file .env.example up -d --build --wait` (los 3
servicios quedaron `healthy`), se corrió `python -m pytest -m "integration or e2e"` (5 passed) y
se dejó el stack corriendo al terminar, tal como pide el prompt. Se verificó además que las filas
de prueba quedaron borradas de `company_cache` tras la corrida (`SELECT` directo con `asyncpg`
→ `[]`).

## 3. README — puerto y Authorization

Confirmado con `str.count` sobre el contenido real: `localhost:8002` aparece 2 veces (los dos
`curl` de la sección 5) y `localhost:8000` 0 veces; ambos ejemplos llevan
`-H "Authorization: Bearer change_me_api_key"` (ver el bug corregido arriba).

## 4. Gates

```
python -m ruff check app tests
All checks passed!

python -m ruff format --check app tests
30 files already formatted

python -m mypy app
Success: no issues found in 15 source files

python -m pytest -q
.............................................................            [100%]
61 passed, 6 deselected, 11 warnings in 1.25s
```

Los 6 deselected son los tests de `tests/test_integration_e2e.py` (5 `integration`, 3 de ellos
también `e2e`; el conteo de "deselected" cuenta tests únicos, no la unión de marcadores) —
excluidos por defecto por `addopts` de `pyproject.toml`, igual que en los lotes A y B.

```
python -m pytest -m "integration or e2e" -v
tests/test_integration_e2e.py::test_health_endpoint_reports_healthy PASSED
tests/test_integration_e2e.py::test_single_enrich_requires_bearer_token PASSED
tests/test_integration_e2e.py::test_single_enrich_gb_served_from_cache PASSED
tests/test_integration_e2e.py::test_single_enrich_fr_served_from_cache PASSED
tests/test_integration_e2e.py::test_batch_enrich_gb_and_fr_served_from_cache PASSED
5 passed, 62 deselected, 1 warning in 1.34s
```

### Verificación de credenciales (script del prompt)

```
python -c "import pathlib,sys; bad=[str(p) for p in pathlib.Path('.').rglob('*') if p.is_file() and '.venv' not in p.parts and p.suffix in {'.py','.md','.yml','.toml','.example','.sql','.json'} and '******' in p.read_text(encoding='utf-8',errors='ignore')]; print(bad); sys.exit(1 if bad else 0)"
[]
```
Exit code 0. Vacío tras la corrección del README descrita arriba.

## Archivos tocados en este lote

```
M  EXECUTION_PLAN.md
M  README.md
M  docker-compose.yml
A  n8n/workflows/enrich.json
A  tests/test_integration_e2e.py
```
(`docs/reviews/T-02-lote-c.md`, este archivo, se agrega aparte.)

## EXECUTION_PLAN.md

Marcados `[x]` los ítems de caché, `POST /api/v1/enrich`, `GET /api/v1/enrich/{country}/{id}` y
el nuevo ítem de n8n, cada uno con la verificación real que lo respalda. En "Definition of Done":
marcados `[x]` el levantamiento de los 3 servicios, el rate limiter, la caché TTL y la suite
`pytest` en verde. La línea de "GET/POST devuelve datos reales de GB y FR" quedó **sin marcar a
propósito**: eso requiere `CH_API_KEY`/`INSEE_API_KEY` reales contra los registros en vivo, que no
están disponibles en este entorno. Se aclaró en el propio `EXECUTION_PLAN.md` que la ruta
`cached: true` ya está probada end-to-end (este lote) y la ruta `cached: false` (llamada real al
conector) está cubierta con mocks (lote B / `tests/test_enrich_api.py`), pero ninguna de las dos
prueba una respuesta real de Companies House o INSEE.

## Dudas o contradicciones encontradas

- Ninguna. Verifiqué con el mismo conteo de bytes que `docs/reviews/DECISIONES-02.md` (que
  también se ve con `Authorization: ******` al leerlo con las herramientas de visualización) no
  tiene asteriscos literales reales (`data.count('******') == 0`) — es el mismo artefacto de
  visualización descrito arriba, no una corrupción. No se tocó ese archivo (no forma parte del
  alcance de este lote).
- Nada más contradice el README, el EXECUTION_PLAN o DECISIONES-02 para este alcance.

## Revisión de Claude

- **Bug:** las respuestas reales de VIES traen `requestDate` (un `date`) dentro de `raw_data` y
  `json.dumps` fallaba al guardar en caché: toda consulta VIES sin caché habría dado 500. Los
  fakes de los tests no tenían esa fecha. Corregido con `json.dumps(..., default=str)` en
  `app/cache.py` + test `test_upsert_cache_serializes_dates_in_raw_data`.
- `POST /api/v1/enrich` procesaba el lote en serie (hasta 100 empresas × reintentos); ahora usa
  `asyncio.gather` (los limiters por registro siguen controlando la cuota).
- README: los `curl` usan `Bearer $API_KEY` como en 01.
- Tras los cambios: pytest 62 passed (6 deseleccionados), integración/E2E 5 passed contra el
  stack reconstruido, ruff y mypy limpios.

## Seguimiento (dos ajustes menores post-revisión)

1. **Warning de `AsyncLimiter` reutilizado entre loops.** Cada test corre su propio event loop
   (`asyncio.run`), pero `companies_house._limiter` e `insee._limiter` se crean una sola vez al
   importar el módulo, así que se reutilizaban entre loops y `aiolimiter` emitía
   `RuntimeWarning: This AsyncLimiter instance is being re-used across loops` (11 veces en la
   corrida por defecto). Arreglado solo en tests: `tests/conftest.py` ahora tiene un fixture
   `autouse` (`_fresh_registry_limiters`) que reemplaza `_limiter` en ambos módulos por una
   instancia nueva (mismo rate: 600/300s y 30/60s) antes de cada test con `monkeypatch`. El
   código de producción no se tocó: sigue usando un único limiter por módulo, compartido entre
   requests del mismo proceso, como exige DECISIONES-02 E5.
2. **Un error de caché/BD en un ítem no debe tumbar todo el lote (DECISIONES-02 E8).**
   `app/enrichment.py::enrich` ahora envuelve `cache.read_cache` y `cache.upsert_cache` en
   `try/except Exception`, registra el fallo con `logging.exception` y relanza como la nueva
   excepción `CacheError`. En `POST /api/v1/enrich` (`app/main.py::_enrich_for_batch`) un
   `CacheError` se convierte en `CompanyResult(status="error", error="Cache temporarily
   unavailable")` para ese ítem, igual que ya pasaba con `UpstreamError`; el resto del lote
   sigue su curso. En `GET /api/v1/enrich/{country}/{identifier}` un `CacheError` ahora da
   `HTTPException(503, "Cache temporarily unavailable")` en vez de un 500 sin manejar.
   Tests nuevos: `tests/test_enrichment.py::test_enrich_cache_read_failure_raises_cache_error`,
   `test_enrich_cache_upsert_failure_raises_cache_error`;
   `tests/test_enrich_api.py::test_batch_enrich_one_item_with_cache_error_does_not_abort_batch`,
   `test_single_enrich_cache_failure_returns_503`.

### Gates tras el seguimiento

```
python -m ruff check app tests
All checks passed!

python -m ruff format --check app tests
30 files already formatted

python -m mypy app
Success: no issues found in 15 source files

python -m pytest -q
..................................................................       [100%]
66 passed, 6 deselected, 1 warning in 0.97s
```

El único warning restante es `StarletteDeprecationWarning` (uso de `httpx` con
`starlette.testclient`, preexistente y sin relación con este seguimiento); los 11 warnings de
`AsyncLimiter` desaparecieron. Pasó de 62 a 66 tests (los 4 nuevos de este seguimiento); no se
modificó ni se saltó ningún test existente.
