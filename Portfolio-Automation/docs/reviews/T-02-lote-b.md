# T-02 — Lote B

Alcance: EXECUTION_PLAN ítems 4-6 (conectores VIES, Companies House, INSEE) + README paso 7
(logging de `api_logs`), siguiendo DECISIONES-02 E5 y E6.

## Archivos creados

```
app/registries/
├── exceptions.py       # RegistryNotFoundError / RegistryError
├── retry_utils.py       # call_with_retries(): tenacity sobre 429/5xx/red/fault, wait configurable
├── api_log.py            # log_api_call(): INSERT en api_logs, nunca propaga su propio fallo
├── companies_house.py
├── insee.py
└── vies.py

tests/
├── test_companies_house.py
├── test_insee.py
├── test_vies.py
├── test_rate_limiter.py
└── test_api_log.py
```

No se tocó ningún otro archivo del lote A.

## Diseño común (E5)

- `lookup()` async en cada conector, siempre envuelto en `try/except/finally`: el `finally`
  llama a `log_api_call(...)` (éxito o error), midiendo `response_time_ms` con
  `time.monotonic()`. Un 404 lanza `RegistryNotFoundError` **sin reintentar**; cualquier otro
  fallo tras agotar reintentos lanza `RegistryError`. Ninguna excepción de `log_api_call`
  puede escapar (ver `api_log.py`): atrapa todo con `except Exception` y usa `logging.exception`.
- `app/registries/retry_utils.py` centraliza `tenacity.AsyncRetrying` (hasta 5 intentos,
  `wait_exponential(multiplier=wait_seconds, min=wait_seconds)`) para los tres conectores.
  `wait_seconds=0` en tests elimina la espera real; en producción el default es `1.0`. Solo se
  reintenta `RetryableRegistryError` (429/5xx/fault SOAP, marcada explícitamente por cada
  conector) o `httpx.TransportError` (errores de red).
- `_build_client()` en cada conector HTTP (CH/INSEE) es una función de módulo aparte para poder
  inyectar `httpx.MockTransport` en los tests sin tocar credenciales reales ni hacer llamadas en
  vivo.
- Ningún endpoint ni credencial aparece en los mensajes de error ni en `endpoint` (solo URL +
  identificador de empresa, nunca la API key — INSEE va en header, CH en Basic Auth, no en la
  URL registrada).

## Companies House (`app/registries/companies_house.py`)

`GET /company/{number}` con Basic Auth (`CH_API_KEY`, password vacío), `AsyncLimiter(600, 300)`
a nivel de módulo. Normalización: `company_name`, `status` = `company_status.lower()` (tal cual,
sin mapeo — DECISIONES E5), `incorporation_date` = `date.fromisoformat(date_of_creation)`,
`raw_data` = el JSON completo.

## INSEE (`app/registries/insee.py`)

`GET /api-sirene/3.11/siren/{siren}` con header `X-INSEE-Api-Key-Integration`, `AsyncLimiter(30,
60)`. `status`: `A`→`active`, `C`→`ceased`. `incorporation_date` = `dateCreationUniteLegale`
(campo estable, a nivel de `uniteLegale`, tal como dice E5).

**Desviación respecto a E5 (anotada como pide la propia decisión):** `denominationUniteLegale` y
`etatAdministratifUniteLegale` **no** están al nivel superior de `uniteLegale` en la API Sirene
3.11 real — son atributos historizados que solo existen dentro de cada elemento de
`periodesUniteLegale` (confirmado contra código de referencia público: p. ej.
`annuaire-entreprises-data-gouv-fr/site`, que lee `periodesUniteLegale` para el nombre y estado
actuales). Se tomó el primer elemento del arreglo (`periodesUniteLegale[0]`, el periodo con
`dateFin: null`, es decir el vigente) para `company_name` y `status`. `dateCreationUniteLegale`
sí es un campo estable de `uniteLegale` como decía la decisión.

## VIES (`app/registries/vies.py`)

`zeep.Client(WSDL_URL)` contra `checkVatService`, llamado con `asyncio.to_thread` (zeep es
síncrono). Sin limiter (VIES no publica cuota). Reintenta `zeep.exceptions.Fault` y
`zeep.exceptions.TransportError`; cualquier otro resultado se normaliza directamente.
**`valid`/`invalid` son ambas respuestas exitosas** (DECISIONES E7: "invalid" no es
"not found"), así que `lookup()` nunca lanza `RegistryNotFoundError` para VIES — solo
`RegistryError` si el fault persiste tras 5 intentos. `incorporation_date` siempre `None`.

## Tests (E6, sin llamadas en vivo)

- **`test_companies_house.py` / `test_insee.py`**: `httpx.MockTransport` inyectado vía
  `_build_client`. Casos: éxito, 404 (sin reintento, se verifica contando llamadas al handler),
  429→200 (reintentado y exitoso), 5xx×5 (falla tras exactamente 5 intentos), y fallo de
  escritura en `api_logs` que no rompe el lookup (se rompe `get_engine` y se verifica que el
  resultado sigue llegando).
- **`test_vies.py`**: cliente zeep falso (`_FakeClient`/`_FakeService`) en vez de mockear HTTP —
  zeep no expone un transporte HTTP trivial de mockear a este nivel, y lo que hay que probar es
  la lógica del conector (reintento, normalización, logging), no la librería zeep en sí. Casos:
  válido, inválido (respuesta exitosa, no error), fault→éxito (reintentado), fault×5 (falla tras
  5 intentos), fallo de `api_logs` no rompe el lookup. Un test adicional marcado `@pytest.mark.live`
  contra el `checkVatTestService` real con el número `100` (siempre válido), excluido por
  `addopts` de `pyproject.toml` (ya tenía `not live` desde el lote A).
- **`test_rate_limiter.py`**: instancias *nuevas* de `AsyncLimiter(600, 300)` y
  `AsyncLimiter(30, 60)` (no el singleton de producción, para no agotar la cuota del módulo real
  entre tests). Tras agotar la capacidad, `has_capacity()` es `False` y un `acquire()` extra
  expira con `asyncio.wait_for(..., timeout=0.2)`. Todo corre dentro de una sola corrutina
  (`asyncio.run`) para mantener el mismo event loop entre el drenado y la verificación —
  `AsyncLimiter` liga su reloj interno al loop en que se usó por primera vez.
- **`test_api_log.py`**: `log_api_call` con un engine falso — inserta fila en éxito, inserta fila
  en error, y si el engine falla al escribir, el error se captura con `caplog` y la función no
  propaga la excepción.
- No se usó `pytest-asyncio` (igual que el lote A: conflicto de versión con `pytest==8.3.2`); las
  funciones de test son síncronas y llaman `asyncio.run(...)` para ejecutar las corrutinas, sin
  dependencias nuevas.

## Falso positivo de redacción de credenciales

Antes de escribir nada se verificó empíricamente que `create`/`edit` **sí escriben** los bytes
reales de una URL con credenciales en el archivo — la sustitución por asteriscos ocurre solo en
la capa de visualización (`view`, `grep`, salida de `powershell`), no en el contenido del archivo.
Se confirmó con `python -c "open(...,'rb').read()"` sobre `.env.example`,
`tests/conftest.py` y `tests/test_config.py`: sus `DATABASE_URL` ya contenían las credenciales
reales (`postgresql://postgres:change_me_postgres_password@postgres:...` y
`postgresql://...@localhost:5432/test`) pese a que el lote A las mostraba enmascaradas al
reportarlas. No se modificó ningún archivo por esta causa — el script de verificación de
credenciales pedido en el prompt confirma que no hay una máscara de asteriscos literal en
ningún archivo del repo (ver salida abajo).

## Verificación real

### Gates

```
python -m ruff check app tests
All checks passed!

python -m ruff format --check app tests
24 files already formatted

python -m mypy app
Success: no issues found in 13 source files

python -m pytest --timeout=60 --cov -p no:cacheprovider
...
tests\test_api_log.py ...                                                [  6%]
tests\test_companies_house.py .....                                      [ 18%]
tests\test_config.py .....                                               [ 30%]
tests\test_health.py ..                                                  [ 34%]
tests\test_insee.py ......                                               [ 48%]
tests\test_models.py ............                                        [ 76%]
tests\test_rate_limiter.py ..                                            [ 81%]
tests\test_security.py ...                                               [ 88%]
tests\test_vies.py .....                                                 [100%]
...
Name                                Stmts   Miss  Cover
-------------------------------------------------------
app\__init__.py                         0      0   100%
app\config.py                           8      0   100%
app\database.py                        14      6    57%
app\main.py                            10      0   100%
app\models.py                          72      0   100%
app\registries\__init__.py              0      0   100%
app\registries\api_log.py              10      0   100%
app\registries\companies_house.py      47      2    96%
app\registries\exceptions.py            2      0   100%
app\registries\insee.py                52      2    96%
app\registries\retry_utils.py          13      2    85%
app\registries\vies.py                 37      3    92%
app\security.py                         9      0   100%
-------------------------------------------------------
TOTAL                                 274     15    95%
43 passed, 1 deselected, 10 warnings in 2.58s
```

Tests: **43 passed** (esperado por el lote: suite completa en verde sin llamadas en vivo), 1
deselected (el test `live` de VIES, excluido por defecto a propósito). Cobertura total 95%.
`database.py` sigue al 57% — no cambia en este lote; la rama de conexión real a Postgres solo
se ejerce con Docker (cubierto en el lote A).

Los 10 warnings son: 1 `StarletteDeprecationWarning` (ya existía en el lote A, por la
combinación FastAPI/Starlette/httpx) + 9 `RuntimeWarning: This AsyncLimiter instance is being
re-used across loops` — artefacto de que cada test llama a `asyncio.run()` por separado (un
event loop nuevo cada vez) mientras el limiter de cada conector es un singleton de módulo creado
una sola vez. No afecta el resultado ni representa un fallo: en producción la app FastAPI corre
en un único event loop durante toda su vida, así que el limiter nunca cambia de loop.

### Verificación de credenciales (script del prompt)

```
python -c "import pathlib,sys; bad=[str(p) for p in pathlib.Path('.').rglob('*') if p.is_file() and '.venv' not in p.parts and p.suffix in {'.py','.md','.yml','.toml','.example','.sql','.json'} and '******' in p.read_text(encoding='utf-8',errors='ignore')]; print(bad); sys.exit(1 if bad else 0)"
[]
```
Exit code 0. No se encontró ninguna máscara de asteriscos literal en el repo (la única
coincidencia posible sería el propio comando citado arriba, que forma parte de la salida real
pedida en el prompt — no es una credencial corrompida).

## EXECUTION_PLAN.md

Marcados `[x]` los tres ítems de conectores (4-6: VIES, Companies House, INSEE) con las
verificaciones reales de arriba. El ítem de logging (README paso 7) no tiene una casilla propia
en el checklist de `EXECUTION_PLAN.md` — quedó implementado como parte del trabajo de los tres
conectores (cada `lookup()` llama a `log_api_call` en su `finally`), cubierto por
`tests/test_api_log.py` y por las aserciones de logging dentro de cada test de conector.

## Dudas o contradicciones encontradas

- Ver la desviación de INSEE arriba (`periodesUniteLegale` vs. nivel superior de `uniteLegale`):
  seguida la documentación/código real de la API Sirene 3.11 en lugar de una lectura literal de
  E5, tal como la propia decisión autoriza ("Si la documentación oficial actual dice otra cosa,
  sigue la documentación y anótalo").
- Ninguna otra contradicción entre README, EXECUTION_PLAN y DECISIONES-02 para este alcance.

## Revisión de Claude

- Limiter: el `async with _limiter` envolvía todos los reintentos, así que 5 intentos gastaban 1
  solo cupo y podían pasarse de la cuota. Movido a `_fetch` en CH e INSEE: cada intento toma cupo.
- VIES: el cliente zeep se creaba en cada consulta (descarga y parseo del WSDL cada vez) y un fallo
  al bajar el WSDL (`requests`) no se reintentaba. Cliente cacheado con `functools.cache` y errores
  de `requests` marcados como reintentables.
- Pendiente para el lote C: INSEE no tiene `denominationUniteLegale` para empresarios individuales
  (usan `nomUniteLegale`/`prenom1UniteLegale`); hoy `company_name` queda `null` en ese caso.
- Tras los cambios: pytest 43 passed (1 live deseleccionado), ruff y mypy limpios.
