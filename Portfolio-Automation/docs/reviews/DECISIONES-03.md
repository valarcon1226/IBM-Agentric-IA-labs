# Decisiones para construir `03-multi-channel-notifier`

Escritas por Claude **antes** de la ejecución. Mandan sobre el README y el EXECUTION_PLAN cuando
los contradigan. Si algo no está aquí y bloquea, detente y repórtalo; si no bloquea, elige lo más
simple, anótalo en el reporte y sigue. Regla general: la solución más simple que funcione,
reutilizando patrones de `02-business-registry-enricher` (config, security, database, healthchecks,
tests de integración); nunca recortes validación, manejo de errores ni seguridad.

## N1 — Estructura, versiones y puertos

- Estructura del README §7, plana como 02: `app/`, `tests/`, `Dockerfile` (uno solo para `api` y
  `worker`), `docker-compose.yml`, `init-db.sql`, `requirements*.txt`, `pyproject.toml`,
  `.env.example`, `.gitignore`. Agrega solo `app/config.py`, `app/security.py`,
  `app/templating.py` (`render_template`) y `app/workers/common.py` si hace falta código compartido.
- Python 3.12, `.venv` ya creado en la raíz. Dev tools con las versiones de 02. Librerías nuevas
  (`celery[redis]`, `jinja2`, `psycopg[binary]` para el worker): versión fija, anotada.
- Puertos del host (los de 01 y 02 están ocupados): `api` `8003:8000`, `postgres` `5435:5432`,
  `redis` `6380:6379`, `mailpit` UI `8026:8025` (SMTP sin publicar). Actualiza los `curl`.

## N2 — Sin tabla `templates`

- El plan menciona una tabla `templates`, pero el README §4 dice que las plantillas viven en
  `app/templates/*.j2`. Gana el README: solo `notifications` y `delivery_logs`.

## N3 — Configuración, secretos y autenticación (igual que 01/02)

- pydantic-settings. Requeridas: `DATABASE_URL`, `CELERY_BROKER_URL`, `API_KEY`. Opcionales (un
  canal sin configurar se rechaza, ver N6): `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`,
  `SMTP_PASSWORD`, `SMTP_FROM`, `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_API_BASE` (defecto `https://api.telegram.org`).
- Bearer `API_KEY` en todas las rutas menos `/health`. `.env.example` con `change_me_<nombre>`.
- Las URLs de webhook salen **solo** de la configuración, nunca del request (sin SSRF). Nunca
  registres tokens ni URLs de webhook completas en logs, `delivery_logs` ni respuestas.

## N4 — Infra de desarrollo para poder probar sin cuentas reales

- `mailpit` (`axllent/mailpit`) como servidor SMTP de desarrollo: el correo se ve en su UI.
- `webhook-sink` (`mendhak/http-https-echo`) que responde 200 a cualquier POST: en `.env.example`
  `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL` y `TELEGRAM_API_BASE` apuntan a él. Así el smoke test
  y el E2E recorren los 4 canales de verdad, sin credenciales. Con valores reales en `.env`, el
  mismo código envía a Slack/Discord/Telegram/SendGrid.

## N5 — Plantillas

- `app/templates/<name>.j2`: texto plano, usado por todos los canales. Opcional
  `<name>.html.j2`: cuerpo HTML del email (autoescape activado). Asunto del email:
  `payload["subject"]` si viene, si no el nombre de la plantilla en formato título.
- Plantillas iniciales: `welcome_email`, `slack_alert`, `daily_report` (las del README §5).
- `StrictUndefined`: si falta una variable, error. La API renderiza **antes** de encolar, así una
  plantilla inexistente o una variable faltante dan 422 y no se crea la notificación.
  `template_name` validado con `^[a-z0-9_]+$` (nada de rutas).

## N6 — Request y validación

- `channels`: subconjunto no vacío y sin repetidos de `email`, `slack`, `telegram`, `discord`.
- `priority`: `low` | `medium` | `high` (defecto `medium`).
- `recipients`: obligatorio para `email` (lista de emails válidos, máx. 50) y `telegram` (chat ids
  `^-?\d+$`, máx. 50). Para `slack` y `discord` el webhook define el destino: sus recipients son
  opcionales y solo se guardan.
- Canal pedido pero no configurado → 422 con el nombre del canal. Payload JSON máx. ~10 KB.

## N7 — Tareas Celery

- Una tarea por canal y notificación (email con todos sus destinatarios en un solo envío; Telegram
  un `sendMessage` por chat id dentro de la misma tarea).
- `autoretry_for` errores transitorios (timeout, conexión, `smtplib.SMTPServerDisconnected`,
  HTTP 429/5xx), `retry_backoff=True`, `retry_jitter=True`, `max_retries=5`. 4xx no se reintenta.
- `rate_limit`: slack `1/s`, discord `5/s`, telegram `30/s`. `ignore_result=True`, sin result
  backend. `priority` → `apply_async(priority=...)` (high=0, medium=5, low=9; en Redis es
  aproximado, anótalo).
- Cada intento escribe una fila en `delivery_logs` (`channel`, `status` = `delivered` |
  `retrying` | `failed`, `attempt_number`, `error_message` corto sin secretos). El worker usa SQL
  plano síncrono (`psycopg`), un pool/engine cacheado.
- Estado de `notifications`: `queued` → `completed` cuando todos los canales quedan `delivered`;
  `failed` si alguno queda `failed` definitivo; actualiza `updated_at`. Evita carreras: calcula el
  estado en un solo `UPDATE ... WHERE id=:id` a partir de `delivery_logs`.

## N8 — Endpoints

- Los 4 del README §5. `GET /notifications`: filtros `status` y `since` (fecha ISO), `limit`
  (defecto 50, máx. 200) y `total`. `GET /notifications/{id}`: 404 si no existe.
- `GET /health`: 200 si Postgres y Redis responden, 503 si no.

## N9 — Tests

- Unit: plantillas (render, variable faltante, nombre inválido), modelos, config, security,
  tareas con clientes mockeados (éxito: el cliente se llama una vez; timeout → retry; 4xx → sin
  retry, `failed`), endpoints con DB y `.delay/apply_async` mockeados.
- Integración/E2E (marcados, excluidos por defecto, skip limpio si el stack no está arriba): POST
  con `["email", "slack"]` → esperar → exactamente 2 filas `delivered` en `delivery_logs`, el
  correo visible en la API de mailpit, y estado `completed`. Limpia lo que crees.
- Reintento visible: con el stack arriba, apunta un canal a un host que no responde (o SMTP con
  timeout) y muestra en el reporte las líneas del log del worker con los reintentos.

## N10 — Qué no hacer

- No agregues RabbitMQ, Alembic, result backend de Celery ni una tabla `templates`.
- No hagas commit ni push. No toques archivos `.env`.
- Cada lote termina con un reporte `docs/reviews/T-03-<lote>.md` con la salida real de cada
  comando; si algo falla o queda bloqueado, dilo tal cual.
