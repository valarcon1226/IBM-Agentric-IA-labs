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

## Estado de los servicios (25 sep, 12:50)

Los 4 servicios (`scout`, `tailor`, `freelance`, `trends`) y el dashboard están **arriba**. Las APIs gratuitas están sin cupo hasta el reset diario; scout/tailor siguen con Ollama, freelance espera cupo.
