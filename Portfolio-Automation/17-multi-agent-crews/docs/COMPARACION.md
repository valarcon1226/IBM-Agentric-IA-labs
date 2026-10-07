# CrewAI vs AutoGen: el mismo equipo en los dos frameworks

Mismo flujo (investigador → analista → redactor → revisor), mismas instrucciones (`app/crews/prompts.py`), mismas
herramientas (`app/tools.py`) y mismo modelo, para que la diferencia sea solo el framework.

| | CrewAI 1.x | AutoGen 0.7 (agentchat) |
|---|---|---|
| Modelo mental | Tareas con un agente responsable, en un proceso (secuencial o jerárquico) | Agentes que conversan en un equipo (round-robin, selector, swarm) |
| Orden de ejecución | Lo fija la lista de tareas | Lo fija el tipo de equipo; termina con una condición (`TERMINATE` o máximo de mensajes) |
| Herramientas | `@tool` de `crewai.tools` | Funciones Python normales con type hints y docstring |
| Modelos que no son de OpenAI | `LLM(model="openai/<modelo>", base_url=...)` | Hay que declarar `model_info` (function calling, visión, JSON) |
| Asincronía | Síncrono (`kickoff`), con variante async | Async nativo (`await team.run(...)`) |
| Contar llamadas al LLM | `token_usage.successful_requests` **cuenta de más** (24 para 6 llamadas reales): se cuentan los eventos `LLMCallCompletedEvent` | Un `models_usage` por respuesta del modelo en `result.messages` |
| Salida | `CrewOutput.raw` (+ salida pydantic opcional) | Lista de mensajes; el informe es el último del revisor |

**Cuándo usar cada uno**
- **CrewAI:** procesos de negocio con pasos conocidos y responsables claros (investigar → redactar → revisar),
  donde importa que el orden sea predecible y fácil de leer.
- **AutoGen:** problemas abiertos donde los agentes deben discutir, iterar o decidir quién habla (selector), y
  sistemas async que ya viven en un event loop.

**Decisión de diseño:** el informe estructurado (`Report`) se arma leyendo las secciones del Markdown final en
vez de pedirle JSON a un modelo local de 4B, que lo rompe con frecuencia. Las fuentes no las declara el modelo:
las registra la herramienta de búsqueda, así que no se pueden inventar.

<!-- measured -->
## Medición (2026-10-07, fake LLM (deterministic), 3 corridas por motor)

| Engine | Avg seconds | Avg LLM calls | Complete reports | Lines of code (non-blank) |
|---|---|---|---|---|
| CrewAI | 0.5 | 6.0 | 3/3 | 62 |
| AutoGen | 0.0 | 6.0 | 3/3 | 62 |

Con el modelo falso, el tiempo mide solo el costo del framework (CrewAI arma más contexto y orquesta más), no la
calidad. Con `qwen3:4b` en el homelab (GPU compartida, ~5 tokens/s) una sola llamada tarda 3–4 minutos, así que una
corrida de AutoGen no terminó en 25 minutos. La medición con modelo real queda para una GPU libre
(`python scripts/compare.py --runs 3` con `LLM_BASE_URL` apuntando a Ollama).
