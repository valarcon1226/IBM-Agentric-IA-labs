# Progreso — bitácora de trabajo

Documento vivo para retomar el trabajo sin re-descubrir contexto. Lo actualiza quien termine
una tarea (agente o persona). Lo más reciente va primero en cada sección.

**Última actualización:** 2026-09-25 (Claude Code)

## Dónde estamos

- **Rama de trabajo:** `portfolio-automation` (no trabajar directo en `main`).
- **GitHub:** `valarcon1226/IBM-Agentric-IA-labs` — **repo público**.
  - PR #1 (línea base: fixes del 04, CI, docs de riesgos, plan de tareas) → **merged** en `main` (`e9333c5`), CI verde.
  - PR #2 (T11: contraseñas de P10 fuera del código) → **abierto**, CI verde. Falta el merge.
- **Proyecto 04:** 27 tests, 58% de cobertura, ruff + mypy limpios, en CI.
- **Proyecto 10:** contraseñas movidas a `.env` (T11). El backend todavía tiene el health check falso,
  el 200 cuando está degradado y el secreto JWT ignorado (DL-R01..R03, R05, R10) → T12.
- **Resto de proyectos (01–03, 05–09, 11, 12):** solo diseño (README + EXECUTION_PLAN), sin código.

## Estado de las tareas (`docs/tasks/`)

| Tarea | Estado | Notas |
| ----- | ------ | ----- |
| T11 | DONE (PR #2) | Ejecutada por Gemini, corregida por Claude: PowerShell había vaciado los `${...}` del compose |
| T12 | **Siguiente** | Backend de P10: health real (200/503), JWT desde archivo, tests, CI |
| T01–T10 | Pendientes | Proyecto 04: persistencia de jobs/schemas, Excel/JSON, cobertura, docs |
| T13 | Pendiente | Proyectos nuevos. Fase 1 (solo lectura) cuando sea; Fases 2–4 después de T06 |

Orden recomendado: merge del PR #2 → T12 → T01…T06 → proyecto 01 (T13) → T07…T10.

## Cómo se trabaja

1. Un agente (Gemini o Copilot) ejecuta **una** tarea de `docs/tasks/` siguiendo
   `.github/copilot-instructions.md` (Gemini lo carga vía `GEMINI.md`). No hace commits.
2. Claude Code revisa el diff contra el código EXACTO de la tarea y corre las verificaciones.
   Luego hace el commit en `portfolio-automation`, abre el PR y espera el CI.
3. Merge a `main` solo con el CI en verde.

## Lecciones aprendidas (ya convertidas en reglas)

- **Gemini + PowerShell:** escribir archivos vía strings de PowerShell expande `${VAR}` a vacío
  (T11 dejó el compose sin contraseñas). Regla: solo herramientas de edición.
- **No maquillar las verificaciones:** Gemini reescribió texto de documentación para que un
  `Select-String` pasara. Regla: reportar el falso positivo, no editar el texto.
- **Una tarea por sesión, sin subagentes:** en la revisión pre-push los subagentes de Antigravity
  se quedaron esperando aprobación de comandos y el orquestador los mató sin entregar el reporte.
- **Push protection de GitHub:** bloquea ejemplos con formato de secreto real (p. ej. un webhook
  `hooks.slack.com/services/T...`). En los ejemplos usar `<placeholder>`.
- **Verificar lo que un comando realmente comprueba:** `docker compose config -q` acepta valores
  vacíos. Hay que verificar el valor resuelto (`config | grep change_me_...`).

## Riesgos abiertos importantes

- **DL-R11:** el stack de P10 nunca se ha levantado (Docker Desktop apagado en esta máquina).
- **DC-R04 / DC-R07 / DC-R09 (04):** el estado de los jobs no se guarda, los schemas viven en
  memoria y solo se acepta CSV → T01–T08.
- Detalle completo: `04-data-cleaning-api/docs/RISK-ANALYSIS.md` y `10-docker-compose-lab/docs/RISK-ANALYSIS.md`.

## Entorno local (Windows)

- `python` no está en el PATH: usar `py -3` o el venv del proyecto (`04-data-cleaning-api\.venv`,
  que se crea con `uv venv -p 3.12 .venv`).
- Docker CLI disponible, **daemon apagado**: `docker compose config` funciona; `up` y los tests de
  integración no.
- Rutas largas en el directorio temporal rompen los venvs: crearlos dentro del proyecto.

## Mensaje listo para la siguiente tarea (T12)

```
Ejecuta SOLO la tarea T12: `Portfolio-Automation/docs/tasks/T12-p10-backend-health-real-y-ci.md`.
Antes, lee completos `Portfolio-Automation/GEMINI.md` y `Portfolio-Automation/.github/copilot-instructions.md`
(tienen dos reglas nuevas: nada de escribir archivos vía PowerShell y nada de cambiar texto para pasar verificaciones).
Confirma que estás en la rama `portfolio-automation`. No uses subagentes. No hagas git add, commit ni push.
Al terminar, pega el reporte (salida real de las verificaciones 1–7), marca T12 como DONE y DETENTE.
```
