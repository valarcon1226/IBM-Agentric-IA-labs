# T-03 — Lote B

Alcance: EXECUTION_PLAN ítems 5-6, DECISIONES-03 N6 (fix de revisión), N7 y N8. Base: T-03-lote-a.md
(estructura, `init-db.sql`, `celery_app.py` sin tareas, plantillas, `config.py`/`security.py`/
`database.py`/`models.py`, `main.py` solo con `/health`).

## 1 — Fix de revisión: inyección de headers vía `payload["subject"]`

`app/templating.email_subject()` ya devolvía `payload["subject"]` tal cual para usarlo como
header `Subject` del email. Un `subject` con `\r` o `\n` permite inyectar headers/cuerpo
adicionales (SMTP header injection clásico).

- **Rechazo (422), no solo saneo:** nuevo `model_validator` en `app/models.py`
  (`validate_subject_no_header_injection`): si `payload["subject"]` es un string y contiene `\r`
  o `\n`, `ValueError` → 422 antes de que la notificación llegue a crearse o a encolarse.
- **Defensa en profundidad:** `email_subject()` también quita `\r`/`\n` del subject que recibe,
  así el helper nunca puede producir un valor inyectado por sí solo aunque se lo llame fuera del
  flujo de `NotifyRequest`.
- Tests nuevos en `tests/test_models.py`: `test_payload_subject_with_crlf_rejected`,
  `test_payload_subject_with_lf_only_rejected`, `test_payload_subject_clean_accepted`.

## 2 — Tareas Celery por canal (DECISIONES-03 N7)

`app/workers/common.py` (nuevo, compartido por las 4 tareas):

- `TransientDeliveryError` / `PermanentDeliveryError`: únicas dos categorías de fallo. Solo la
  primera dispara reintento.
- `post_webhook_json(url, payload)`: POST JSON con `urllib.request` (stdlib, sin agregar
  dependencias nuevas — regla ponytail). Clasifica por código HTTP: 429 o 5xx → transitorio,
  cualquier otro 4xx → permanente. El mensaje de error nunca incluye la URL (solo el código HTTP
  o el nombre de la excepción), así nunca se filtran tokens ni URLs completas de webhook (N3).
- `log_delivery_attempt(notification_id, channel, status, attempt_number, error_message)`:
  inserta una fila en `delivery_logs` y recalcula `notifications.status` en un único
  `UPDATE ... FROM (...)` (CTE con `delivery_logs` + las claves de `recipients` como fuente de
  verdad de qué canales se pidieron) — sin condición de carrera entre tareas concurrentes del
  mismo `notification_id` (N7). Usa `psycopg` síncrono (como ya estaba pineado en requirements.txt
  desde el lote A, sin usar hasta ahora) con una conexión por llamada — los workers Celery son
  procesos síncronos separados del engine `asyncpg` de la API.
- `PRIORITY_TO_CELERY = {"high": 0, "medium": 5, "low": 9}` (N7, aproximado en Redis).

**Decisión de diseño — de dónde sale el conjunto de canales pedidos:** el schema de
`notifications` (lote A, sin cambios) no tiene columna `channels`. En vez de agregarla, el
endpoint `/notify` guarda en `recipients` (JSONB, ya existente) una clave por cada canal pedido,
incluso con lista vacía para slack/discord sin destinatarios explícitos ("el webhook define el
destino", N6). Así `jsonb_object_keys(recipients)` es siempre el conjunto completo de canales
pedidos, y el recompute de estado no necesita tocar el schema. Anotado también en el docstring de
`common.py`.

**Tareas** (`email_task.py`, `slack_task.py`, `discord_task.py`, `telegram_task.py`):

- Cada una: `@celery_app.task(bind=True, max_retries=5, retry_backoff=True, retry_jitter=True)`
  más `rate_limit` donde aplica (slack `1/s`, discord `5/s`, telegram `30/s`; email sin límite,
  no estaba en el alcance de N7). **No se usó el parámetro `autoretry_for`** literal: en su lugar,
  cada tarea atrapa explícitamente `TransientDeliveryError`/`PermanentDeliveryError` y decide
  entre loguear+reintentar o loguear+terminar. Motivo: `autoretry_for` no da un punto donde
  escribir la fila de `delivery_logs` *antes* de reintentar o fallar definitivamente — el reintento
  manual (`self.retry(exc=...)`) usa exactamente los mismos atributos `retry_backoff`/
  `retry_jitter`/`max_retries` del Task (Celery los lee dentro de `Task.retry()` sea cual sea el
  mecanismo que lo invoque), así que el backoff con jitter es idéntico; solo cambia que hay
  logging por intento. Anotado en el EXECUTION_PLAN.
- `email_task.py`: `smtplib` + `email.message.EmailMessage`, cuerpo de texto siempre, parte HTML
  opcional (`add_alternative`). Solo llama `smtp.login()` si el servidor anuncia `AUTH`
  (`has_extn("auth")`) — mailpit en dev no lo soporta; SendGrid/real SMTP en prod sí. Clasificación
  de errores: `TimeoutError`/`ConnectionError`/`SMTPServerDisconnected`/`SMTPConnectError`/
  `SMTPHeloError` → transitorio; `SMTPResponseException` con código 4xx → transitorio, cualquier
  otro código → permanente; cualquier otro `SMTPException` → permanente (catch-all). **Nota:**
  `smtplib.SMTPException` hereda de `OSError`, así que no se puede incluir `OSError` genérico en
  la tupla de "transitorio" sin que también atrape errores permanentes como
  `SMTPRecipientsRefused` — se encontró este bug con el test
  `test_email_permanent_failure_no_retry` (fallaba porque `OSError` capturaba todo primero) y se
  corrigió quitando `OSError` de esa tupla.
- `slack_task.py` / `discord_task.py`: un solo `post_webhook_json` por notificación, con
  `{"text": ...}` / `{"content": ...}` respectivamente. El destino es siempre
  `settings.SLACK_WEBHOOK_URL`/`settings.DISCORD_WEBHOOK_URL` — nunca algo del request (N3, sin
  SSRF).
- `telegram_task.py`: un `sendMessage` por `chat_id` dentro de la misma tarea (N7). Si alguno falla
  transitoriamente, se reintenta toda la tarea (puede re-enviar a chat ids que ya tuvieron éxito —
  aceptable, at-least-once, y mucho más simple que un estado de reintento por destinatario que el
  schema de `delivery_logs` de todos modos no tiene dónde guardar). Si ninguno es transitorio pero
  alguno es permanente, falla sin reintentar.
- `app/workers/celery_app.py`: agregado `include=[...]` con los 4 módulos de tareas (en el lote A
  quedó vacío a propósito) y configuración de prioridad para Redis
  (`task_queue_max_priority=9`, `task_default_priority=5`, `broker_transport_options` con
  `priority_steps`).

## 3 — Endpoints (DECISIONES-03 N8)

`app/notifications.py` (nuevo, capa de acceso a datos async, mismo patrón que
`02-business-registry-enricher/app/cache.py`: `sqlalchemy` async engine + `text()` parametrizado,
sin ORM): `insert_notification`, `get_notification` (con sus `delivery_logs`), `list_notifications`
(filtros `status`/`since`, `LIMIT`, `COUNT(*)` con los mismos filtros).

`app/main.py` — los 4 endpoints de README §5, Bearer en todos menos `/health` (ya existente):

- `POST /api/v1/notify`: renderiza **antes** de encolar (`render_template`/`render_html_template`/
  `email_subject`) — plantilla desconocida o variable faltante → 422, sin crear la notificación
  (N5/N8). Arma `recipients` con una clave por canal pedido (ver sección 2). Inserta la
  notificación, luego `apply_async(priority=...)` una tarea por canal pedido (no `.delay()`,
  porque `.delay()` no acepta `priority`).
- `GET /api/v1/notifications/{id}`: 404 si el `id` no es un UUID válido o si no existe la fila.
- `GET /api/v1/notifications`: filtros `status`, `since` (ISO 8601, 422 si no parsea), `limit`
  (default 50, máx. 200 — `Query(..., le=200)`, 422 si se excede), `total`.
- `GET /api/v1/templates`: `app.templating.available_templates()`.

## 4 — Tests unitarios nuevos (N9)

- `tests/test_models.py`: 3 tests nuevos de inyección de subject (ver sección 1).
- `tests/test_workers_common.py` (nuevo): clasificación HTTP de `post_webhook_json` (200 OK, 429 y
  5xx transitorios, 404 permanente, error de red transitorio, y que el mensaje de error nunca
  incluye la URL/token), y que `log_delivery_attempt` ejecuta exactamente un `INSERT` y un
  `UPDATE` (con una conexión psycopg mockeada, sin Postgres real).
- `tests/test_workers.py` (nuevo): para las 4 tareas — éxito (el cliente mockeado se llama
  exactamente una vez, log `delivered`), error transitorio (reintenta vía `self.retry()` mockeado,
  log `retrying`), error permanente (sin reintento, log `failed`); además para email, reintentos
  agotados (`retries == max_retries`) → `failed` sin reintentar; para telegram, una llamada al
  cliente mockeado por cada `chat_id`.
- `tests/test_notify_endpoint.py` (nuevo): `POST /notify` con DB y `apply_async` mockeados
  (encolado exitoso con `notification_id`/`status=queued`, prioridad `high`→`0` propagada a
  `apply_async`; 422 por canal desconocido, plantilla desconocida, variable de plantilla
  faltante), `GET /notifications/{id}` (401 sin token, 404 con UUID malformado, 404 no encontrado,
  200 con `delivery_logs`), `GET /notifications` (401, límite >200 → 422, filtros pasados a la
  capa de datos, `since` inválido → 422), `GET /templates` (401, 200 con la lista real).

## Verificación real

### Gates

```
python -m ruff check app tests
All checks passed!

python -m ruff format --check app tests
25 files already formatted

python -m mypy app
Success: no issues found in 15 source files

python -m pytest --timeout=60 --cov -p no:cacheprovider
tests\test_config.py ......                                              [  7%]
tests\test_health.py ..                                                  [  9%]
tests\test_models.py ........................                            [ 39%]
tests\test_notify_endpoint.py ................                           [ 58%]
tests\test_security.py ...                                               [ 62%]
tests\test_templates.py ...........                                      [ 75%]
tests\test_workers.py .............                                      [ 91%]
tests\test_workers_common.py .......                                     [100%]

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
app\workers\common.py             34      1    97%
app\workers\discord_task.py       19      2    89%
app\workers\email_task.py         43      5    88%
app\workers\slack_task.py         19      2    89%
app\workers\telegram_task.py      33      2    94%
--------------------------------------------------
TOTAL                            455     60    87%
82 passed in 2.64s
```

`app/notifications.py` queda en 24% (ramas de filtro/paginación no ejercidas por los mocks) y
`database.py` sigue en 58% — ambos se ejercen de verdad contra Postgres real en la sección
siguiente, no en el suite unitario mockeado.

### Docker real (rebuild + smoke test, DECISIONES-03 N1/N4)

```
docker compose --env-file .env.example up -d --build --wait
...
 Container 03-multi-channel-notifier-redis-1 Healthy
 Container 03-multi-channel-notifier-webhook-sink-1 Healthy
 Container 03-multi-channel-notifier-mailpit-1 Healthy
 Container 03-multi-channel-notifier-postgres-1 Healthy
 Container 03-multi-channel-notifier-worker-1 Healthy
 Container 03-multi-channel-notifier-api-1 Healthy

docker compose --env-file .env.example ps
NAME                                        STATUS                    PORTS
03-multi-channel-notifier-api-1            Up (healthy)   0.0.0.0:8003->8000/tcp
03-multi-channel-notifier-mailpit-1        Up (healthy)   0.0.0.0:8026->8025/tcp
03-multi-channel-notifier-postgres-1       Up (healthy)   0.0.0.0:5435->5432/tcp
03-multi-channel-notifier-redis-1          Up (healthy)   0.0.0.0:6380->6379/tcp
03-multi-channel-notifier-webhook-sink-1   Up (healthy)
03-multi-channel-notifier-worker-1         Up (healthy)
```

Payload del README §5 adaptado a N6 (puerto `8003`, `Authorization: Bearer change_me_api_key` de
`.env.example`, canales `email` + `slack`):

```
POST http://localhost:8003/api/v1/notify
{
  "template_name": "welcome_email",
  "channels": ["email", "slack"],
  "priority": "high",
  "recipients": {"email": ["alice@example.com"], "slack": ["#alerts"]},
  "payload": {"user_name": "Alice", "system": "Data Intake Pipeline"}
}

200
{"notification_id":"8ea8b268-60a4-447b-9234-664a78be68aa","status":"queued","message":"Notification queued for processing."}
```

`delivery_logs` (vía `docker compose exec -T postgres psql`, 2 filas, ambas `delivered` en el
primer intento):

```
            notification_id            | channel |  status   | attempt_number | error_message
--------------------------------------+---------+-----------+----------------+---------------
 8ea8b268-60a4-447b-9234-664a78be68aa | slack   | delivered |              1 |
 8ea8b268-60a4-447b-9234-664a78be68aa | email   | delivered |              1 |
(2 rows)
```

Estado de la notificación (ambos canales `delivered` → `completed`, recalculado por el `UPDATE`
único de `log_delivery_attempt`):

```
                  id                  |  status   | template_name | priority
--------------------------------------+-----------+---------------+----------
 8ea8b268-60a4-447b-9234-664a78be68aa | completed | welcome_email | high
(1 row)
```

Email en la API de mailpit (`GET http://localhost:8026/api/v1/messages`):

```
total: 1
Welcome Email | [{'Name': '', 'Address': 'alice@example.com'}] | {'Name': '', 'Address': 'notifier@example.com'}
```

(Subject = "Welcome Email", el fallback de `email_subject()` en Title Case — el payload de este
POST no incluía `"subject"`.)

Log del worker (los 4 nombres de tarea registrados, ambas tareas de este envío recibidas y
exitosas en el primer intento):

```
[tasks]
  . tasks.send_discord
  . tasks.send_email
  . tasks.send_slack
  . tasks.send_telegram

Task tasks.send_email[...] received
Task tasks.send_slack[...] received
Task tasks.send_slack[...] succeeded in 0.063s: None
Task tasks.send_email[...] succeeded in 0.076s: None
```

Endpoints `GET` verificados contra el stack real (todos con el mismo Bearer):

```
GET /api/v1/notifications/8ea8b268-60a4-447b-9234-664a78be68aa -> 200
{"id":"...","template_name":"welcome_email","status":"completed","created_at":"...",
 "delivery_logs":[{"channel":"slack","status":"delivered","processed_at":"..."},
                   {"channel":"email","status":"delivered","processed_at":"..."}]}

GET /api/v1/notifications?limit=5 -> 200
{"results":[{"id":"...","template_name":"welcome_email","status":"completed","created_at":"..."}],"total":1}

GET /api/v1/templates -> 200
{"templates":["daily_report","slack_alert","welcome_email"]}
```

El stack se dejó corriendo (instrucción explícita del lote).

### Verificación de credenciales

```
python -c "import pathlib,sys; bad=[str(p) for p in pathlib.Path('.').rglob('*') if p.is_file() and '.venv' not in p.parts and p.suffix in {'.py','.md','.yml','.toml','.example','.sql','.json','.j2'} and '******' in p.read_text(encoding='utf-8',errors='ignore')]; print(bad); sys.exit(1 if bad else 0)"
[]
```

Ningún archivo del proyecto contiene el patrón de redacción. Ninguna URL con credenciales se
escribió directamente con editores de texto en este lote (los nuevos archivos no contienen URLs
con `user:password@`; `DATABASE_URL` nunca se tocó).

## EXECUTION_PLAN.md

Marcados `[x]` los tres ítems restantes del checklist (tareas por canal, endpoint `/notify` +
los otros tres endpoints, smoke test con stack real) y el primer ítem de la sección "Definition of
Done" que faltaba, cada uno con una nota remitiendo a este reporte para la desviación de
`autoretry_for`/`.delay()`. El ítem "SMTP timeout retried… visible en worker logs" quedó sin marcar
`[x]`: está cubierto por el test unitario mockeado, no por una demostración en vivo contra el
stack (ver "Dudas" abajo).

## Dudas o contradicciones encontradas

- **`psql -c` interactivo bloqueado de nuevo:** igual que en el lote A, `docker compose exec
  postgres psql ... -c "..."` fue denegado sin pedir aprobación ("Permission denied and could not
  request permission from user"). Se resolvió agregando `-T` a `docker compose exec` (modo no
  interactivo), que sí funcionó y dio el mismo resultado verificado contra la base real.
- **Demostración en vivo de reintento (N9 "reintento visible"):** el reintento por timeout/error
  transitorio está cubierto por 3 tests unitarios mockeados
  (`test_email_timeout_retries`, `test_webhook_transient_error_retries` ×2,
  `test_telegram_transient_error_retries`) que verifican el log `retrying` y la llamada a
  `self.retry()`. No se reprodujo además contra el stack Docker real (p. ej. apuntando
  `SLACK_WEBHOOK_URL` a un host que no responde) porque eso requeriría reiniciar el worker en
  vivo con una variable de entorno distinta a la de `.env.example`, lo cual el lote no pidió
  explícitamente (sí pidió mostrar los 2 `delivery_logs` `delivered`, el estado y el correo en
  mailpit — los tres se muestran arriba). Si se quiere esa demostración en vivo, se puede hacer en
  un lote posterior sin tocar `.env`.
- **`autoretry_for` vs reintento manual:** anotado en la sección 2 y en EXECUTION_PLAN.md —
  decisión tomada porque el reintento manual permite loguear cada intento en `delivery_logs`
  *antes* de decidir reintentar o fallar, algo que el decorador `autoretry_for` no expone
  directamente. El comportamiento de backoff/jitter/`max_retries` es idéntico (son atributos del
  `Task` que `Task.retry()` lee sin importar quién lo invoque).
- Ninguna otra contradicción entre README, EXECUTION_PLAN y DECISIONES-03 para este alcance.
