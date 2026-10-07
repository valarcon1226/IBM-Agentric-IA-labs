# 17-A · Equipo multi-agente en CrewAI y AutoGen (investigación de mercado)

Carpeta nueva: `Portfolio-Automation/17-multi-agent-crews` (solo esta). Imita vacantes de AI Engineer que piden
"CrewAI, AutoGen, multi-agent systems, cloud deployment" (63 y 62 vacantes en jobHunter).

1. Un mismo flujo en los dos frameworks (versiones estables vigentes, fijadas en `requirements.txt`):
   investigador → analista → redactor → revisor. Entrada: un tema (ej. "demanda de chatbots de WhatsApp para
   restaurantes en LATAM"). Salida: informe Markdown con hallazgos, fuentes y recomendaciones.
   `app/crews/crewai_crew.py` y `app/crews/autogen_team.py` con la MISMA interfaz `run(topic) -> Report`.
2. Herramientas de los agentes: búsqueda sobre una carpeta `corpus/` (10–15 documentos de ejemplo, escritos por ti,
   marcados como ficticios) y una herramienta de cálculo simple. Sin APIs de pago.
3. LLM configurable por `.env` con cualquier endpoint compatible con OpenAI (por defecto Ollama
   `http://localhost:11434/v1`, modelo `qwen3:4b`). Para tests: un LLM falso determinista, como
   `14-n8n-automation-pack/fake-llm/server.py` (reutiliza la idea; no copies código que no uses).
4. API FastAPI: `POST /reports {topic, engine: "crewai"|"autogen"}` → id; `GET /reports/{id}` → estado e informe.
   Trabajo en segundo plano simple (BackgroundTasks), guardado en SQLite. `GET /health`.
5. `Dockerfile` + `docker-compose.yml` (api + fake-llm). Tests pytest: los dos motores con el LLM falso, la API
   de punta a punta, errores (tema vacío, motor inválido). `ruff` limpio.
6. `docs/COMPARACION.md`: tabla CrewAI vs AutoGen (líneas de código, tiempo y llamadas al LLM medidos en una corrida
   real con Ollama si está disponible, o con el falso y dilo), cuándo usar cada uno. `README.md` en inglés
   (es para vacantes) con diagrama Mermaid, cómo correrlo y un informe de ejemplo en `samples/`.

Verificación (pega la salida real): `pytest -q`, `ruff check .`, `docker compose up -d --build`,
`curl` de crear y leer un informe con cada motor, y al final `docker compose down`.

Reglas: la solución más simple que funcione (ponytail). Sin commit ni push. Sin `.env` reales (solo `.env.example`).
Sin secretos. No toques otras carpetas. Si algo te bloquea, detente y explícalo.
Al terminar escribe `docs/reviews/T-17-A.md` (español) con la salida real de cada comando.
