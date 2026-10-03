# jobHunter — Estado del proyecto

_Última actualización: 2026-09-25_

## Dónde corre ahora

Todo el pipeline corre **24/7 en el homelab** (`homeLab1`, `ssh valentina@192.168.1.15`), en Docker, en `~/homelab/jobhunter`.
La IP cambió de `192.168.2.12` a `192.168.1.15` → **pendiente: reservarla en el router (DHCP)**.

| Servicio | Qué hace | Frecuencia |
|---|---|---|
| `scout` | Busca vacantes (JobSpy: LinkedIn/Indeed; Glassdoor da 403) | cada 6h |
| `tailor` | Genera CV (desde template por arquetipo) + guía de estudio | continuo |
| `freelance` | Proyectos pequeños (plata + portafolio) | cada 12h |
| `trends` | Tendencias del mercado freelance | cada 24h |
| `hustles-dashboard` | Dashboard en vivo → **http://192.168.1.15:8100** | siempre |

Comandos útiles:
```bash
ssh valentina@192.168.1.15 "cd ~/homelab/jobhunter && docker compose ps"
ssh valentina@192.168.1.15 "cd ~/homelab/jobhunter && docker compose logs --tail 50 scout"
ssh valentina@192.168.1.15 "cd ~/homelab/jobhunter && docker compose up -d"   # levantar todo
```
Para desplegar cambios: `scp archivo.py valentina@192.168.1.15:~/homelab/jobhunter/` (el código está montado, no hace falta rebuild salvo cambios en `requirements.txt`/`Dockerfile`).

> ⚠️ La `jobs.db` del **homelab** es la fuente de verdad. La copia de la laptop está desactualizada — no correr scout/tailor en ambos lados.

## Qué se hizo (24–25 sep)

- **Homelab**: Dockerfile + `docker-compose.yml` con los 4 servicios; dashboard desplegado leyendo la misma DB y los CVs.
- **LLM sin tope diario**: `llm_chain.py` agrega **Ollama `qwen3:4b`** (GTX 1050 4GB) como último escalón tras Gemini → Groq → OpenRouter. Config clave: `num_ctx=4096` (8192 se derrama a CPU, ~3 tok/s) y salida restringida al JSON schema (con `format="json"` a secas devolvía el perfil). Parámetro `allow_local=False` para llamadas donde la calidad importa.
- **Templates por arquetipo**: `ai_engineer`, `forward_deployed_engineer`, `qa_automation` en `archetype_templates/`. AI Engineer y FDE regenerados para abrir como *"AI Full Stack Engineer…"* (QA como diferenciador). Backup de los anteriores en `archetype_templates/backup_20260924/`.
- **Bugs corregidos**:
  - `database.save_job` devolvía a `Aprobado` vacantes que ya tenían CV → el tailor las regeneraba. Ahora no retrocede estados.
  - Dashboard no encontraba CVs con rutas de Windows en Linux.
- **Filtros del scout sin LLM** (`job_filters.py`): URL ya evaluada / misma empresa+título, pasantías, idioma ≠ en/es, sin descripción. `linkedin_fetch_description=True` en el scraper (antes LinkedIn venía sin descripción y se evaluaba solo por el título).
- **Freelance rehecho** (`freelance_scraper.py`, `freelance_hunter_agent.py`): API pública de Freelancer.com filtrada por skills + bounties de GitHub (Algora). Filtros previos: presupuesto $50–1500 o ≥$15/h, ≤60 propuestas, blocklist (ventas, data entry, cripto…), ≤3 bounties por repo. El LLM puntúa `portfolio_value` (0–10), días estimados y entregable. **Solo usa APIs** (`allow_local=False`).

## Números (25 sep)

154 vacantes (97 nuevas desde el 24/09) · 118 con CV · 12 pendientes · 12 filtradas · **0 postulaciones marcadas** · Freelance: 0 evaluadas (sin cupo de API, ver abajo) · Trends: 18 tendencias nuevas.

## 🔴 Problema abierto: el modelo local infla los match

En 24h Ollama hizo ~356 de ~450 llamadas. `qwen3:4b` puntúa ~85% casi todo (75 de 97 vacantes nuevas), y aprobó roles no técnicos (Campaign Operations, Salesforce Marketing). Además scout/tailor consumen el cupo de las APIs antes de que le toque a `freelance`.

### Evaluación en 2 pasos (`job_scoring.py`) — ✅ en producción desde el 25/09 ~12:45
1. El LLM solo **extrae hechos** de la JD (`JobFacts`: rol técnico, familia de rol, años, skills obligatorias/deseables, restricción de país, presencialidad, idiomas).
2. **Python calcula el match** de forma determinística contra `master_profile.json`.

**Validación** (`validate_scoring.py`, 31 vacantes, solo modelo local, contra lo que había dado Gemini — resultado en `~/homelab/jobhunter/validation.log`):
- ✅ Descarta bien los 3 casos malos conocidos (75→5, 75→5, 65→11).
- ✅ Detecta restricciones que Gemini dejó pasar (ciudadanía EE.UU., presencial/híbrido, senior 5+ años).
- ✅ Puntajes variados (20 valores distintos) y explicables.
- ⚠️ **Demasiado estricto**: promedio 34 vs 73 antes. Causas encontradas al revisar los hechos extraídos:
  - El modelo mete **tecnologías de más como "obligatorias"** (Newpage: 22 obligatorias; CrowdStrike: NIST, MITRE, SOC…) → la cobertura cae.
  - El matching de skills es muy literal: `"Fast API"`, `"Lang Graph"`, `"Chroma"`, `"JSON"`, `"Regular Expressions"` no se reconocen como skills que ella tiene.
  - Cala Health: extrajo `country_restricted` y `onsite` = True → hay que verificar contra la JD si es real.

### Hecho el 25/09 (tarde)
- `job_scoring.py` ajustado: normaliza espacios/guiones ("Fast API", "Lang Graph"), más alias (Chroma, JSON, regex, CI/CD, pandas), solo las primeras 6 obligatorias. `country_restricted` ya no marca ofertas en Colombia/LATAM que piden "autorización en el país de la oferta" (falso positivo en FullStack).
- `scout_agent.evaluate_viability_and_gaps` ahora usa `job_scoring` (el prompt holístico viejo quedó sin uso).
- Re-evaluadas las 9 vacantes `Aprobado`: solo quedan **2** (Norton Rose Fulbright 80%, FullStack Colombia 55%); las otras 7 → `Match Insuficiente` (no técnicas, EE.UU./clearance, presencial, senior 8+).
- **Freelance en 2 pasos** (como `job_scoring`): el LLM solo extrae `GigFacts` (categoría, skills pedidas, alcance claro, días, entregable) **sin el perfil** (~500 tokens vs ~3.5k), y `score_gig` calcula match (70% cobertura de skills con el vocabulario de `job_scoring` + 30% valor de portafolio por categoría; -15 si el alcance es vago; bounties +3 de portafolio). Descarta non_technical, full_product y >15 días. Ahora **sí usa Ollama** → ya no se frena por cupo. De paso se eliminó el sesgo de `salary_expectation` (rechazaba gigs comparando con EUR 3–4k/mes).
- Blocklist freelance + automatización industrial (PLC, Siemens, PCB, SCADA, HMI…), que traía la skill "Automation" de Freelancer.
- Quedan 9 gigs con veredicto del LLM viejo (`Descartado` sin `[Filtro]`); no se re-evalúan solos. Opcional: borrarlos a mano para que se reconsideren.
- Trends: excluye bounties de GitHub (issues sueltos) y la blocklist (cripto, ventas…) antes de analizar; descarta tendencias con < 2 menciones.

### Próximos pasos
1. Re-correr `validate_scoring.py` con el ajuste y comparar (no se hizo: ~35 min de GPU compitiendo con scout).
2. ⏳ Re-evaluando las 146 vacantes `CV Generado` (lanzado 25/09 ~16:00, `rescore.py` en el contenedor `trends`, log en `~/homelab/jobhunter/rescore_cv.log`, termina con `FIN`). Las que no pasan → `Match Insuficiente` (el PDF queda en `CVs_Listos`). Backup previo: `jobs.db.bak_before_rescore_20260925`.
3. ✅ Freelance funcionando (25/09 tarde): 2 corridas → **11 gigs `Aplicable`**. Intervalo bajado a 6h (`FREELANCE_INTERVAL_HOURS=6` en `.env` del homelab). Chequeo sin LLM: `python test_freelance_scoring.py`. Revisar a mano los repos de bounties `SecureBananaLabs/bug-bounty` y `UnsafeLabs/Bounty-Hunters` (miles de issues con $780/$310: pueden ser granjas); si lo son, agregarlos a un bloqueo por repo.
4. Pendientes de Valentina: reservar IP en el router; Tailscale para acceso remoto (opcional); empezar a postular y marcarlo en el dashboard.
5. Código commiteado en `portfolio-automation` (`6eeb785`, sin push). `jobHunter/.gitignore` es lista blanca: solo `*.py`, Dockerfile, compose, requirements y este archivo — nunca `.env`, `auth_state.json`, `jobs.db`, CVs ni el perfil.

## Cambios 28 sep — cupo de nube solo para lo irremplazable

- Disco del homelab liberado (slskd/soulsync fuera): 18% usado.
- Scout cada 2h (`SCOUT_INTERVAL_HOURS=2` en `.env`), freelance cada 6h.
- **Tailor**: `archetypes.needs_adjustment` solo ajusta si el gap pide una skill que ella SÍ tiene (está en el master profile) y el template no la dice. Antes ajustaba por skills que le faltan → 2-5 llamadas perdidas y el revisor igual devolvía el template. Guía de estudio → `invoke_text(local_only=True)` (Ollama).
- **Trend Spotter rehecho**: busca nichos vendibles (tarea/problema que el mercado paga, ej. "draft legal contracts"), no skills. Cada hora Ollama anota `domain/task/deliverable/automatable` de cada vacante/gig nuevo en `demand_signals` (una vez por URL, máx. `TRENDS_MAX_PER_RUN`=60). Python agrupa (difflib). 1 llamada a la nube cada 20h para el reporte (nicho, agente, cómo venderlo); sin cupo, sale el conteo crudo. Chequeo: `python test_trend_grouping.py`.
- **Más cupo gratis** en `llm_chain.py` (cupos por modelo): Gemini 3.8/3.7/3.5/3.5-lite flash, Groq qwen3.8-27b y gpt-oss-20b. Gemini con `max_retries=1, timeout=90` (antes un 429/503 colgaba la cadena minutos). Gemma 4 descartado (>50s por respuesta).
- **Franjas de match 9-5** (scout): 70+ → CV · 40–69 → visible sin CV (`Match Insuficiente`) · <40 o no viable → `No Elegible` (oculta, guardada para no re-evaluar). Plan de estudio solo 50–89% (link en el dashboard); 90+ solo gaps. Dashboard con filtro por % (botones 90+/70–89/50–69/40–49).
- **Puntaje 100% técnico** (`job_scoring.score`): el rol es REQUISITO (solo `ai_engineer`, `forward_deployed`, `qa_automation`; el resto se descarta) y ya no suma puntos. pct = 80% obligatorias + 20% deseables (solo obligatorias si no hay deseables) − penalización por años. Re-puntuado con `rescore.py` (Ollama, log `rescore_tech.log`, backup `jobs.db.bak_before_tech_score_20260928`).
- **Local primero (30/09)**: la cadena probaba la nube antes que Ollama, así que el scout (extracción de hechos de cada vacante, 90%+ de las llamadas) agotaba todo el cupo gratis antes de las 10 am. Ahora `scout_agent` (`SCOUT_LOCAL_ONLY`, default 1) y `freelance_hunter_agent.extract_gig_facts` usan solo Ollama. La nube queda para: reporte diario del Trend Spotter, ajustes puntuales del Tailor, queries del scout (1 por iteración) y herramientas manuales.
- **Búsqueda enfocada del scout**: `SCOUT_QUERIES="a|b"`, `SCOUT_FAMILY=qa_automation`, `SCOUT_YEARS=3-4` → una pasada, lo fuera de foco no se guarda. Corrida QA lanzada el 30/09 (`scout_qa.log`, contenedor `jobhunter-scout-qa`).
## Cambios 1–3 oct
- **Ubicación**: scout busca LinkedIn en Colombia / Latin America / United States (sin Indeed/Glassdoor). `job_filters.location_reason`: fuera de Colombia solo pasa si contratan desde LATAM o como contractor internacional sin pedir papeles (`test_location_filter.py`). Columna `jobs.location`; `locate_jobs.py` la completó desde LinkedIn y ocultó ~300 vacantes de otros países.
- **Aprendizaje** (`learning_plan.py` → `learning_plan.json` → pestaña "Aprender"): gaps por skill + rol (AI/FDE/QA/Freelance), plan generado desde cómo lo piden las vacantes, horas calibradas, práctica web y prompt de entrevista; los gaps se revisan contra el perfil actual. Estimaciones a mano solo para herramientas que ya usa (`skill_estimates_curated.json`).
- **CVs en Drive**: `sync_cvs_drive.py` (cron del host cada 30 min, rclone con cliente OAuth propio "jobhunter") sube los CVs visibles y guarda `jobs.cv_link` (link público por archivo).
- **Trend Spotter**: lee también gigs de side hustles (`fetch_hustle_gigs`) y los clasifica en los 10 del video (columna `demand_signals.hustle`, con verificación por palabras clave en `check_hustle`); sección en el reporte.
- **Freelance**: busca web (WordPress/React/Shopify…) y QA; proyectos grandes ya no se descartan (`FREELANCE_MAX_BUDGET_USD`, `FREELANCE_MAX_DAYS`); guarda `category` y `missing_skills`; bloquea hardware industrial.
- **Perfil (homelab)**: + React, WordPress, herramientas de IA (Claude Code, Codex, Gemini CLI, Copilot, Antigravity).
- **Dashboard**: secciones y filtros por rol / tipo de proyecto / side hustle, ubicación, link de CV en Drive, plan de estudio por vacante, orden "Mejor pagados".
- Docs fuera de git (repo público): `PORTFOLIO_PLAN.md` (10 proyectos freelance), `STUDY_ROUTES.md` (rutas WhatsApp y CrewAI), `Profiles/answers.yaml`.

- **Workana** (29/09) agregada a `freelance_scraper.fetch_workana`: página pública `/jobs` (permitida por robots.txt) con UA de navegador, JSON en `results-initials`, ~114 proyectos IT (es+en) por corrida. Probado desde la laptop; **falta desplegar al homelab** (y confirmar que desde su IP no da 403).
- Pendiente: cuentas gratis de Cloudflare Workers AI, Mistral y NVIDIA (claves en `.env`) para sumarlas a la cadena.

## Estado de los servicios (25 sep, 12:50)

Los 4 servicios (`scout`, `tailor`, `freelance`, `trends`) y el dashboard están **arriba**. Las APIs gratuitas están sin cupo hasta el reset diario; scout/tailor siguen con Ollama, freelance espera cupo.
