# Tareas — índice y estado

Ejecuta **una tarea por sesión de chat**, en orden. Excepción: **T11 → T12** (bugs de P10) no
dependen de T01–T10 y se pueden hacer primero. Cómo ejecutarlas: `.github/copilot-instructions.md`.
Para arrancar una tarea, escribe en Copilot (modo Agent):

> Ejecuta la tarea `docs/tasks/T01-job-status-y-modelos.md` siguiendo `.github/copilot-instructions.md`.

Punto de partida verificado (2026-09-24): proyecto 04 con **27 passed**, 58% de cobertura,
ruff y mypy limpios.

| ID  | Archivo | Proyecto | Resultado esperado | Estado |
| --- | ------- | -------- | ------------------ | ------ |
| T01 | [T01-job-status-y-modelos.md](T01-job-status-y-modelos.md) | 04 | 29 passed | PENDIENTE |
| T02 | [T02-jobs-repo.md](T02-jobs-repo.md) | 04 | 29 passed | PENDIENTE |
| T03 | [T03-rutas-crean-job.md](T03-rutas-crean-job.md) | 04 | 31 passed | PENDIENTE |
| T04 | [T04-tareas-celery-persisten-estado.md](T04-tareas-celery-persisten-estado.md) | 04 | 34 passed | PENDIENTE |
| T05 | [T05-rutas-jobs-desde-db.md](T05-rutas-jobs-desde-db.md) | 04 | 38 passed | PENDIENTE |
| T06 | [T06-tests-integracion-postgres.md](T06-tests-integracion-postgres.md) | 04 | 38 passed, 2 deselected | PENDIENTE |
| T07 | [T07-schemas-persistidos.md](T07-schemas-persistidos.md) | 04 | 41 passed, 3 deselected | PENDIENTE |
| T08 | [T08-excel-y-json.md](T08-excel-y-json.md) | 04 | 44 passed, 3 deselected | PENDIENTE |
| T09 | [T09-cobertura-cleaner-transformer-enricher.md](T09-cobertura-cleaner-transformer-enricher.md) | 04 | 53 passed, 3 deselected | PENDIENTE |
| T10 | [T10-docs-proyecto-04.md](T10-docs-proyecto-04.md) | 04 | docs sincronizados | PENDIENTE |
| T11 | [T11-p10-passwords-fuera-del-codigo.md](T11-p10-passwords-fuera-del-codigo.md) | 10 | 0 contraseñas en archivos | PENDIENTE |
| T12 | [T12-p10-backend-health-real-y-ci.md](T12-p10-backend-health-real-y-ci.md) | 10 | 5 passed en backend + CI | PENDIENTE |
| T13 | [T13-protocolo-proyecto-nuevo.md](T13-protocolo-proyecto-nuevo.md) | 01 → … | Fase 1 cuando sea; Fases 2–4 tras T06 | PENDIENTE |

Qué cierra cada tarea (riesgos de `04-data-cleaning-api/docs/RISK-ANALYSIS.md`):
T01–T06 → DC-R04 (estado de jobs) · T07 → DC-R07 (schemas) · T08 → DC-R09 (Excel/JSON) ·
T09 → DC-R02, DC-R11 · T11 → DL-R04 (contraseñas en P10) · T12 → DL-R01, R02, R03, R05, R10 (backend de P10; ver `10-docker-compose-lab/docs/RISK-ANALYSIS.md`).
