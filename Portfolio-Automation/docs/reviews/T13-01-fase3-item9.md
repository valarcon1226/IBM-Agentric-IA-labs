# T13-01 — Fase 3, ítem 9

- 9: `[ ]` workflow n8n de cinco nodos (Webhook → HTTP Request → Wait → Split Out → Google Sheets) exportado a `n8n/workflows/intake.json`. El Webhook recibe el CSV; HTTP Request manda el multipart `file` y `callback_url={{$execution.resumeUrl}}`; Split Out divide `body.clean_rows`; Google Sheets está configurado para append con placeholders.
- D8 implementada: `POST /upload` acepta `callback_url` opcional; la URL se valida contra `N8N_RESUME_BASE_URL` por esquema, host, puerto y prefijo de path antes de escribir el upload. Si no se envía, `process_upload` conserva `N8N_CALLBACK_URL`. El callback lleva los datos de status, la cuenta previa como `clean_rows_count` y el array de filas limpias como `clean_rows`, consultado con SQL parametrizado.
- `N8N_RESUME_BASE_URL=http://n8n:5678/webhook-waiting/` añadido a los ejemplos de entorno. Compose incluye API (necesaria para `http://api:8000`), n8n con `WEBHOOK_URL=http://n8n:5678/` y volumen persistente `n8n_data`.
- No se incluyen API keys, credenciales/tokens Google ni IDs reales. Después de importar se debe seleccionar la credencial Header Auth, crear/seleccionar la credencial Google OAuth2 y reemplazar los placeholders de Spreadsheet ID y nombre de pestaña en n8n.
- `python -m json.tool n8n/workflows/intake.json` → JSON válido; comprobación estructural adicional → `5 nodes, expected order, placeholders present, no bearer token or Google token`.
- `python -m pytest backend frontend/tests -q` → `25 passed, 1 warning` (deprecación Starlette/AnyIO).
- `python -m ruff check app tests` desde `backend/` → `All checks passed!`; Ruff check de `frontend/` con `backend/pyproject.toml` → `All checks passed!`.
- `python -m ruff format --check app tests` desde `backend/` → `15 files already formatted`; Ruff format check de `frontend/` → `2 files already formatted`.
- `python -m mypy app` desde `backend/` → `Success: no issues found in 8 source files`.
- Verificación Docker real (2026-10-01): seis contenedores en ejecución; Postgres y Redis Healthy; API `/health`, dashboard `/`, MinIO `/minio/health/ready` y n8n `/healthz` devolvieron HTTP 200. El healthcheck de API también consultó Postgres, Redis y MinIO.
- Smoke upload `61a7e9f9-4879-4ac1-a088-df6afed0b30b`: `completed`, 3 filas; antes de revisión, 1 en `clean_data`, 1 en `review_queue`, 1 en `error_log`. MinIO listó los objetos originales de los dos uploads de prueba.
- Dashboard real: Aprobar movió Jane a `clean_data` (2 filas clean para el primer upload) y vació su cola; Rechazar en el segundo upload creó `Rejected in review` en `error_log` y vació su cola.
- Suite fresca con `backend/.venv/Scripts/python.exe -m pytest backend frontend/tests -q`: `25 passed, 1 warning` (deprecación Starlette/AnyIO). `python -m json.tool n8n/workflows/intake.json`: válido.
- D7 ya no bloquea las verificaciones Docker. El workflow de cinco nodos está estructuralmente validado y n8n responde, pero no se ejecutó el append de Google Sheets: faltan credenciales Google configuradas en n8n. El ítem 9 permanece pendiente hasta validar esa escritura real.
