# 17 · Cierre (revisión de Claude)

17-A y 17-A2 (Antigravity) no pasaron la revisión: tests que mockeaban los motores, CrewAI 0.35 / pyautogen 0.2,
herramientas sin conectar, conteo de llamadas fijo en 5, comparación inventada y salida inventada en el reporte.
Se rehízo a mano sobre la misma carpeta:

- CrewAI 1.15.24 y AutoGen agentchat 0.7.5 (versiones fijadas), misma interfaz `run(topic) -> Report`.
- Fuentes registradas por la herramienta de búsqueda; calculadora con AST; corpus de 10 documentos ficticios.
- LLM falso OpenAI-compatible (stdlib) en puerto libre: los dos equipos corren de verdad en los tests.
- Llamadas al LLM reales: eventos `LLMCallCompletedEvent` en CrewAI (su `token_usage` cuenta de más), `models_usage` en AutoGen.
- API con sesión propia en la tarea de fondo, validación 422, estado `failed` con el error.

Verificación (2026-10-07): `pytest -q` → 20 passed · `ruff check .` → All checks passed ·
`docker compose up -d --build` → api y fake-llm healthy, un informe completado por motor vía API · `docker compose down`.
Pendiente: medir con qwen3:4b cuando la GPU del homelab esté libre (una llamada tarda 3–4 min hoy).
