# T-03 — Lote C

Alcance: cierre del ítem pendiente del Definition of Done ("A simulated SMTP timeout is retried
by Celery (visible in worker logs) instead of failing immediately") con una demostración real
además del test unitario mockeado, más los tests de integración/E2E contra el stack Docker real
que el lote B había dejado solo descritos en "Dudas". Base: T-03-lote-a.md / T-03-lote-b.md.

Nota: este reporte se escribe tras una interrupción de memoria del lote original. El bug de
`retry_countdown`, su fix, `tests/test_integration_e2e.py` (3 tests), y las actualizaciones de
README/EXECUTION_PLAN ya estaban hechos y verificados antes de la interrupción; lo que sigue
documenta ese trabajo y repite toda la verificación desde cero en esta sesión.

## 1 — Bug de backoff en los reintentos manuales (`app/workers/common.py`)

Las 4 tareas (`email_task.py`, `slack_task.py`, `discord_task.py`, `telegram_task.py`) reintentan
manualmente con `self.retry(exc=..., countdown=...)` en vez de usar el parámetro `autoretry_for`
del decorador (decisión de diseño documentada en T-03-lote-b.md, sección 2: permite loguear cada
intento en `delivery_logs` antes de reintentar o fallar). El problema: `retry_backoff=True` /
`retry_jitter=True` del decorador `@celery_app.task(...)` **solo** tienen efecto cuando es
`autoretry_for` quien dispara el reintento — un `self.retry()` manual sin `countdown` explícito
cae al `default_retry_delay` fijo (180s, sin backoff ni jitter), violando DECISIONES-03 N7
("reintentos con backoff exponencial").

**Fix:** nueva función `retry_countdown(retries: int) -> int` en `app/workers/common.py`, que
llama a `celery.utils.time.get_exponential_backoff_interval(factor=1, retries=retries,
maximum=RETRY_BACKOFF_MAX_SECONDS, full_jitter=True)` — el mismo cálculo que usa internamente la
maquinaria de `retry_backoff=True` de Celery, pero invocado explícitamente desde cada tarea:
`self.retry(exc=exc, countdown=retry_countdown(self.request.retries))`. `RETRY_BACKOFF_MAX_SECONDS
= 600` (10 minutos), el mismo tope por defecto que usa Celery.

Test nuevo en `tests/test_workers_common.py`: verifica que `retry_countdown` delega en
`get_exponential_backoff_interval` con esos parámetros exactos (mockeando la función de Celery, sin
depender de los valores aleatorios del jitter).

## 2 — `tests/test_integration_e2e.py` (nuevo, DECISIONES-03 N9)

Igual patrón que `02-business-registry-enricher/tests/test_integration_e2e.py`: habla contra el
stack real levantado por `docker compose` (API en `http://localhost:8003`, Postgres en
`localhost:5435`, mailpit en `http://localhost:8026`), con un fixture de módulo (`stack`) que hace
`skip` (no `fail`) si el stack no responde, así el suite unitario sigue corriendo sin Docker.
Marcado con `pytestmark = pytest.mark.integration`, y los dos tests de flujo completo llevan
además `@pytest.mark.e2e` — ambos marcadores están excluidos por defecto (ver `pyproject.toml`,
`addopts = -m "not integration and not e2e"`).

Tres tests:
- `test_health_endpoint_reports_healthy`: `GET /health` → 200, sin autenticación.
- `test_email_slack_notification_delivers_and_completes` (`e2e`): `POST /notify` con
  `["email", "slack"]`, hace polling de `GET /notifications/{id}` hasta estado terminal, verifica
  `completed` con 2 `delivery_logs` (`delivered`), lo mismo contra Postgres directo, el email
  visible en la API de mailpit, y que `GET /notifications/{id}` y
  `GET /notifications?status=completed` lo devuelven. Limpieza en `finally`: borra el mensaje de
  mailpit y la notificación (cascada a `delivery_logs` vía `ON DELETE CASCADE`).
- `test_four_channel_notification_reaches_completed` (`e2e`): los 4 canales a la vez
  (`email`+`slack`+`telegram`+`discord`), mismo polling, 4 `delivery_logs` `delivered`, mismo
  `finally` de limpieza.

Conexión a Postgres vía argumentos discretos (`host`/`port`/`user`/`password`/`dbname`), nunca un
DSN único con credenciales embebidas, siguiendo la misma convención que `02`. Todas las variables
de conexión (`E2E_*`) tienen fallback a los valores de `.env.example`.

## 3 — Demostración en vivo del reintento (cierre del DoD pendiente)

El lote B había dejado este punto del DoD sin marcar, señalando en "Dudas" que el reintento solo
estaba cubierto por tests unitarios mockeados y que faltaba una demostración real. Esta sesión la
ejecutó así:

- Se escribió un script temporal de un solo uso (`_retry_demo.py`, en la raíz de
  `03-multi-channel-notifier`, **no** forma parte del código de la app ni del suite de tests) que:
  - Pone `celery_app.conf.task_always_eager = True` / `task_eager_propagates = False` — así
    `send_email_task.apply_async(...)` ejecuta la tarea real (incluida su maquinaria real de
    `self.retry()`/backoff/jitter) en el mismo proceso, sin necesitar un worker ni Redis corriendo.
  - Apunta `SMTP_SERVER=127.0.0.1` / `SMTP_PORT=1` (puerto cerrado local, nada escucha ahí) vía
    variables de entorno — `smtplib.SMTP()` lanza `ConnectionRefusedError` de inmediato, que
    `email_task._send` clasifica como transitorio (`TransientDeliveryError`), igual que un timeout
    real de SMTP.
  - Reemplaza `email_task.log_delivery_attempt` por un logger (en vez de escribir en Postgres,
    ya que el script corre suelto sin tocar la base de datos ni el stack Docker).
- No se tocó el stack Docker real en ningún momento: el script corre con el `python` del venv del
  proyecto, apuntando a un puerto cerrado que no tiene relación con `mailpit` ni con ningún
  servicio del `docker-compose.yml`. Verificado al final (sección "Gates" abajo) que los 6
  contenedores siguen con el mismo *uptime* de antes de esta sesión.

**Salida real del script** (recortada a lo esencial; `max_retries=5`, por lo que hay 5
reintentos — intentos 1 a 5 — y un sexto intento final que agota los reintentos y falla):

```
2026-10-02 20:00:39,528 INFO [t=2.1s] delivery_logs: notification=demo-retry-nid channel=email status=retrying attempt=1 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:39,534 INFO Task tasks.send_email[...] retry: Retry in 1s: TransientDeliveryError('SMTP transient error: ConnectionRefusedError')
2026-10-02 20:00:41,577 INFO [t=4.2s] delivery_logs: notification=demo-retry-nid channel=email status=retrying attempt=2 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:41,578 INFO Task tasks.send_email[...] retry: Retry in 2s: TransientDeliveryError('SMTP transient error: ConnectionRefusedError')
2026-10-02 20:00:43,642 INFO [t=6.2s] delivery_logs: notification=demo-retry-nid channel=email status=retrying attempt=3 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:43,643 INFO Task tasks.send_email[...] retry: Retry in 4s: TransientDeliveryError('SMTP transient error: ConnectionRefusedError')
2026-10-02 20:00:45,681 INFO [t=8.3s] delivery_logs: notification=demo-retry-nid channel=email status=retrying attempt=4 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:45,682 INFO Task tasks.send_email[...] retry: Retry in 0s: TransientDeliveryError('SMTP transient error: ConnectionRefusedError')
2026-10-02 20:00:47,746 INFO [t=10.3s] delivery_logs: notification=demo-retry-nid channel=email status=retrying attempt=5 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:47,748 INFO Task tasks.send_email[...] retry: Retry in 2s: TransientDeliveryError('SMTP transient error: ConnectionRefusedError')
2026-10-02 20:00:49,814 INFO [t=12.4s] delivery_logs: notification=demo-retry-nid channel=email status=failed attempt=6 error=SMTP transient error: ConnectionRefusedError
2026-10-02 20:00:49,832 INFO Task tasks.send_email[...] succeeded in 2.079s: None
2026-10-02 20:00:49,832 INFO Task finished. result.state=SUCCESS
```

Se ven las 5 líneas `retrying` con countdowns crecientes y con jitter (1s, 2s, 4s, 0s, 2s — cada
uno un entero aleatorio entre 0 y `2**retries`, acotado a 600s, por `full_jitter=True`), seguidas
de la línea final `failed` en el intento 6 (`self.request.retries == self.max_retries == 5`
agotó los reintentos). Las líneas `Task ... retry: Retry in Ns: ...` las emite el propio Celery
(no el código de la app), confirmando que el `countdown` calculado por `retry_countdown()` llega
de verdad hasta `Task.retry()`. "Succeeded" al final es el resultado de la tarea Celery en sí
(terminó sin excepción sin propagar, por `task_eager_propagates=False`), no del envío de email —
el envío falló permanentemente tal como se esperaba.

## 4 — Gates (re-ejecutados completos en esta sesión)

### `ruff check`

```
python -m ruff check app tests
All checks passed!
```

### `ruff format --check`

```
python -m ruff format --check app tests
26 files already formatted
```

### `mypy app`

```
python -m mypy app
Success: no issues found in 15 source files
```

### `pytest` (suite por defecto, `integration`/`e2e` excluidos)

```
python -m pytest --timeout=60 --cov -p no:cacheprovider
tests\test_config.py ......                                              [  7%]
tests\test_health.py ..                                                  [  9%]
tests\test_models.py ........................                            [ 38%]
tests\test_notify_endpoint.py ................                           [ 57%]
tests\test_security.py ...                                               [ 61%]
tests\test_templates.py ...........                                      [ 74%]
tests\test_workers.py .............                                      [ 90%]
tests\test_workers_common.py ........                                    [100%]

Name                           Stmts   Miss  Cover
--------------------------------------------------
app\__init__.py                    0      0   100%
app\config.py                     28      0   100%
app\database.py                   19      8    58%
app\main.py                       66      2    97%
app\models.py                    101      0   100%
app\notifications.py              45     34    24%
app\security.py                    9      0   100%
app\templating.py                 35      4    89%
app\workers\__init__.py            0      0   100%
app\workers\celery_app.py          4      0   100%
app\workers\common.py             38      1    97%
app\workers\discord_task.py       19      2    89%
app\workers\email_task.py         43      5    88%
app\workers\slack_task.py         19      2    89%
app\workers\telegram_task.py      33      2    94%
--------------------------------------------------
TOTAL                            459     60    87%
83 passed, 3 deselected in 2.61s
```

83 passed — exactamente lo esperado (el lote B tenía 82; el test nuevo de `retry_countdown` en
`test_workers_common.py` suma 1, y los 3 de `test_integration_e2e.py` quedan deseleccionados por
sus marcadores: 82 + 1 + 3 = 86 recolectados, 83 seleccionados).

### `pytest -m "integration or e2e"` (contra el stack Docker real, sin reconstruir nada)

```
python -m pytest --timeout=60 -p no:cacheprovider -m "integration or e2e" -v
tests/test_integration_e2e.py::test_health_endpoint_reports_healthy PASSED [ 33%]
tests/test_integration_e2e.py::test_email_slack_notification_delivers_and_completes PASSED [ 66%]
tests/test_integration_e2e.py::test_four_channel_notification_reaches_completed PASSED [100%]

3 passed, 83 deselected in 2.32s
```

3 passed, contra el stack ya corriendo (`docker compose --env-file .env.example ps` mostró los 6
contenedores `Up (healthy)` antes y después, mismo *uptime* ~5h, confirmando que ninguno se
reinició ni se reconstruyó durante esta sesión).

## 5 — README.md y EXECUTION_PLAN.md

Ambos ya estaban actualizados antes de la interrupción; revisados y confirmados en esta sesión
(`git diff`, sin más cambios necesarios):

- **README.md:** nota de autenticación (`Authorization: Bearer ...`) agregada antes de la sección
  5, todos los `curl` de ejemplo actualizados al puerto real `8003` y con el header `Authorization`,
  tabla de servicios de la sección 6 ampliada con `mailpit`/`webhook-sink` y puertos de host reales
  (`8003`/`5435`/`6380`/`8026`), y una subsección nueva "Development infrastructure" que explica
  que `.env.example` usa `mailpit` y `webhook-sink` como sustitutos locales sin credenciales reales
  para los 4 canales, con instrucciones de cómo apuntar a servicios reales editando un `.env`
  propio (nunca `.env.example`).
- **EXECUTION_PLAN.md:** los 6 ítems del "Build Checklist" y los 5 del "Definition of Done" quedan
  `[x]`, cada uno con una nota de verificación real y una remisión a T-03-lote-b.md o a este
  reporte. En particular, el ítem "A simulated SMTP timeout is retried..." ahora dice
  explícitamente: cubierto por `tests/test_workers.py::test_email_timeout_retries` (mockeado) *más*
  la demostración en vivo de la sección 3 de este reporte (5 reintentos reales con countdown
  creciente y jitter, luego `failed`), y documenta el bug de `retry_countdown` encontrado y
  corregido. El último ítem anota los números reales: 83 passed (suite por defecto) + 3 passed
  (`integration`/`e2e`) = 86 tests totales.

## Dudas o contradicciones encontradas

- **Script de demostración no se pudo borrar:** `_retry_demo.py` (el script de la sección 3) quedó
  en la raíz de `03-multi-channel-notifier/`. Los dos intentos de `Remove-Item` sobre ese archivo
  en esta sesión fueron denegados por el entorno ("Permission denied and could not request
  permission from user") — no es un error del sistema operativo ni de Docker, es un bloqueo de la
  herramienta de shell de esta sesión ante una operación de borrado. El resto de comandos de
  PowerShell de este mismo lote (gates, `docker compose ps`) corrieron sin problema. El archivo no
  toca ningún servicio, no tiene credenciales reales (usa `127.0.0.1:1` y valores `demo_user`/
  `demo_pass` ficticios) y no está incluido en ningún test ni import de la app — se recomienda
  borrarlo manualmente (`Remove-Item _retry_demo.py`) antes de cualquier commit.
- Ninguna otra contradicción entre README, EXECUTION_PLAN, DECISIONES-03 y el código para este
  alcance.

## Revisión de Claude

- `_retry_demo.py` revisado (script de demo de 56 líneas, sin efectos fuera del proceso) y borrado.
