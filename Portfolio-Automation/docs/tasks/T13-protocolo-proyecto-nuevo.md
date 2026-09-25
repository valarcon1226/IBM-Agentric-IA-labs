# T13 — Protocolo para construir un proyecto nuevo (01, 03, 06, 05, 02, 08, 07, 09, 11, 12)

Úsalo **una vez por proyecto y por sesión**, en este orden (de `docs/BUILD-PLAN.md`):
**01 → 03 → 06 → 05 → 02 → 08 → 07 → 09 → 11 → 12**. P10 se cierra al final con su propio
`EXECUTION_PLAN.md`.

Para arrancar, escribe en Copilot:
> Ejecuta `docs/tasks/T13-protocolo-proyecto-nuevo.md` para el proyecto `01-smart-data-intake`, **solo la Fase 1**.

A diferencia de T01–T12, aquí no hay código EXACTO: el diseño está en el `README.md` de cada
proyecto. Por eso el protocolo se divide en fases cortas y **se detiene después de cada una**
para que Valentina revise.

## Antes de empezar

- **Fase 1** (solo lectura) se puede ejecutar en cualquier momento.
- **Fases 2–4** requieren `T06` en `DONE`: el proyecto 04 debe tener ya el patrón de persistencia
  en Postgres (`jobs_repo`) y de tests de integración (`tests/integration/`) que aquí se copia.
  No dependen de T07–T12.
- El proyecto anterior en el orden está marcado `Implemented` o `Implemented (partial)` en
  `Portfolio-Automation/README.md` (para 01 el anterior es 04: ya lo cumple). Si no, detente.

## Fase 1 — Leer y detectar contradicciones (sin escribir código)

1. Lee completos: `<proyecto>/README.md`, `<proyecto>/EXECUTION_PLAN.md` y `docs/BUILD-PLAN.md`
   (sección "Cross-project decisions").
2. Haz una tabla con **todas** las contradicciones que encuentres. Por ejemplo: README vs
   EXECUTION_PLAN, un endpoint sin modelo de request, una tabla sin columnas definidas, una
   variable de entorno que se usa pero no está listada, o una librería que contradice
   BUILD-PLAN.
3. Para cada librería del stack, anota la versión que vas a fijar y **de dónde** la sacaste (PyPI).
   No uses librerías sin release en los últimos 24 meses sin decirlo en el reporte.
4. **Detente.** Reporta la tabla. No sigas hasta que Valentina responda.

## Fase 2 — Esqueleto y compuertas (sin lógica de negocio)

1. Crea la estructura igual que el proyecto 04: `app/` (`api/routes/`, `core/`, `models/`,
   `services/`), `tests/`, `pyproject.toml` (copia el de 04), `requirements.txt` con versiones
   fijas, `requirements-dev.txt` (`-r requirements.txt` + las mismas herramientas y versiones de
   `04-data-cleaning-api/requirements-dev.txt`), `.env.example`, `.gitignore` (copia el de 04),
   `docker-compose.yml`, `Dockerfile`, `init-db.sql`.
2. Copia los patrones del 04, adaptando solo los nombres:
   - `app/core/config.py` (pydantic-settings, variables requeridas sin valor por defecto);
   - `tests/conftest.py` (valores inertes);
   - `tests/test_config.py` (`.env.example` cumple `Settings`);
   - `app/core/security.py` + `dependencies=[Depends(verify_api_key)]` en `app/main.py` si el
     proyecto expone una API;
   - `/health` que devuelve 503 si una dependencia falla.
3. Test obligatorio `test_production_app_exposes_documented_routes`: importa `app.main:app` y
   comprueba que existen **todas** las rutas del README (sección API). Hoy fallará porque las
   rutas no existen: márcalo en el reporte como "esperado rojo hasta la Fase 3", **sin** `skip`
   ni `xfail`.
4. Compuertas (las del 04, desde la carpeta del proyecto) → todo verde salvo ese test.
5. **Detente** y reporta.

## Fase 3 — Un ítem del EXECUTION_PLAN por vez

Para cada `- [ ]` del `EXECUTION_PLAN.md`, en orden:

1. Implementa **solo** ese ítem.
2. Escribe sus tests (unitarios con fakes, como en el 04; integración con `testcontainers`
   marcada `@pytest.mark.integration`, como en T06, si toca base de datos).
3. Corre las compuertas y el `Verify:` del ítem. Pega la salida.
4. Cambia `- [ ]` → `- [x]` y agrega debajo `  - Done: <salida real resumida>`.
5. Cada **3 ítems**, detente y reporta. No hagas más de 3 sin revisión.

Reglas de la Fase 3:
- El contrato HTTP son los modelos Pydantic de las rutas. Los ejemplos `curl` del README deben
  tener un test que envíe exactamente ese body (como `README_TRANSFORM_PAYLOAD` en el 04).
- Si el README pide algo imposible o contradictorio, detente (ver "Hard rules" en
  `.github/copilot-instructions.md`).

## Fase 4 — Documentación de calidad y CI

1. Crea `docs/RISK-ANALYSIS.md` y `docs/TRACEABILITY-MATRIX.md` con el mismo formato que los del
   04. Usa el prefijo del proyecto en los IDs (01 → `DI-R01`, `DI-UP-001`; 03 → `MN-`;
   06 → `SE-`; 05 → `IP-`; 02 → `BR-`; 08 → `LG-`; 07 → `PM-`; 09 → `NA-`; 11 → `MD-`;
   12 → `CI-`). Los escenarios sin test quedan como `Not Implemented`; cuéntalos con
   `Select-String`, no a mano.
2. Agrega la sección "Current status" arriba del README del proyecto (formato del 04).
3. Agrega el proyecto a `matrix.include` de `.github/workflows/portfolio-automation-ci.yml`
   con `project`, `src: app` y `slug` = nombre de la carpeta. Solo cuando sus compuertas pasen
   localmente.
4. En `Portfolio-Automation/README.md`, cambia su fila de `Designed` a
   `Implemented (partial)` (o `Implemented` si no queda ningún riesgo crítico abierto), con los
   tests y la cobertura reales.
5. **Detente** y reporta. No empieces el siguiente proyecto sin aprobación.
