# 17-A2 · Correcciones del equipo multi-agente (revisión de 17-A)

Carpeta: `Portfolio-Automation/17-multi-agent-crews` (solo esta). La revisión de `docs/reviews/T-17-A.md` encontró que
esto NO cumple `docs/tasks/17-A-multi-agent-crews.md`. Cada punto exige la evidencia indicada; no lo reportes sin ella.

1. **Versiones vigentes**: `crewai==0.35` y `pyautogen==0.2` son de 2024 y las vacantes piden las APIs actuales.
   Usa la última estable de `crewai` y de AutoGen 0.4+ (`autogen-agentchat` + `autogen-ext[openai]`, API nueva:
   `AssistantAgent`, `RoundRobinGroupChat` o `SelectorGroupChat`, `TextMentionTermination`). Quita el parche de
   `setuptools`. Python 3.12. Evidencia: `pip freeze | grep -iE "crewai|autogen"`.
2. **Las herramientas no están conectadas**: `search_corpus` y `calculate` existen pero ningún agente las usa.
   Dáselas al investigador y al analista en los dos motores. `calculate` con `eval` se cuelga con `9**9**99`:
   reemplázalo por un evaluador con `ast` que solo acepte + - * / y paréntesis, con límite de tamaño.
3. **Corpus**: hay 1 documento; la tarea pide 10–15 (ficticios, marcados como tales, sobre demanda de IA/automatización
   en LATAM, con cifras para que el analista calcule). La búsqueda debe rankear por coincidencia de palabras, no
   buscar la frase exacta.
4. **Misma interfaz `run(topic) -> Report`**: crea el modelo `Report` (pydantic: `title`, `findings`, `sources`
   (documentos del corpus usados), `recommendations`, `markdown`, `llm_calls`, `seconds`) y que los dos motores lo
   devuelvan. Guárdalo en la base como JSON.
5. **Tests con el LLM falso, no con mocks**: hoy los tests parchean `run()` y nunca ejecutan CrewAI ni AutoGen.
   Haz que el `fake-llm` responda como OpenAI (incluyendo `tool_calls` cuando el último mensaje lo amerite, para
   probar las herramientas) y que haya un test por motor que corra el equipo completo contra él y verifique el
   `Report` (con fuentes del corpus). Mantén los tests de la API.
6. **Bug de sesión**: `generate_report` usa la sesión de la request después de que se cerró. Abre una sesión nueva
   dentro de la tarea en segundo plano. Test que lo cubra.
7. **COMPARACION.md inventada**: los números (~15 llamadas, ~8 s) no se midieron. Mide de verdad: script
   `scripts/compare.py` que corre ambos motores N=3 veces y escribe la tabla (llamadas al LLM, segundos, líneas de
   código con `wc -l`). Si Ollama (`http://localhost:11434`) responde, mide también con `qwen3:4b`; si no, dilo.
8. **El reporte de 17-A inventó salida** (`'Mocked CrewAI Report' o 'Report on…'`). En el reporte nuevo pega solo
   salida real, completa, copiada de la terminal.
9. **Limpieza**: borra `reports.db`, `test.db` y `test_api_script.py`; agrega `.gitignore` (db, venv, caches).
   Ruta de la base por `.env`. En el compose el `fake-llm` NO publica el puerto 11434 (choca con Ollama).
   Quita `version:` del compose. `README.md`: agrega ejemplo de salida real (`samples/`), cómo usar Ollama y la
   tabla de comparación.

Verificación (salida real completa): `pip freeze | grep -iE "crewai|autogen"`, `pytest -q`, `ruff check .`,
`python scripts/compare.py`, `docker compose up -d --build`, crear y leer un informe por motor con `curl.exe` (o
`Invoke-RestMethod`) y pegar el JSON real, `docker compose down`.

Reglas: ponytail, sin commit ni push, sin `.env` reales, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-17-A2.md` (español) con la salida real de cada comando.
