# 18-A · Servidor MCP de Sabor de Casa + evaluación de agentes

Carpeta nueva: `Portfolio-Automation/18-mcp-agent-evals` (solo esta; solo LEE el 13). Imita vacantes de Forward
Deployed / AI Engineer / QA que piden "Model Context Protocol", "agent testing", "LLM evaluation".

1. Servidor MCP con el SDK oficial de Python (`mcp`, versión fijada; transporte stdio y HTTP): herramientas
   `consultar_menu`, `consultar_horario`, `crear_reserva`, `estado_pedido`, `zonas_domicilio` y un recurso con las
   políticas. Datos: los archivos de `13-whatsapp-restaurant-assistant/knowledge/` (leídos, no copiados a mano) y
   SQLite para reservas/pedidos. Validación de entradas (fechas, personas máx. 12, horario) con errores claros.
2. Un agente cliente que usa el servidor (LangGraph + `langchain-mcp-adapters`, o el cliente MCP del SDK) con LLM
   local por `.env` (Ollama, compatible con OpenAI) y un LLM falso determinista para tests.
3. Suite de evaluación `evals/`: 30 casos en YAML (pregunta, herramienta esperada, argumentos esperados, hechos que
   la respuesta debe contener, cosas que NO debe decir). Métricas: herramienta correcta, argumentos correctos,
   respuesta fundamentada (sin inventar platos ni precios), rechazo de pedidos fuera de política, prompt injection
   básico ("ignora tus instrucciones…"). Reporte `reports/eval.md` + JSON con tasa de acierto por métrica.
4. Tests pytest del servidor (cada herramienta, entradas inválidas) y de la suite (que corre con el LLM falso y da
   100%). Opción `--model` para correr la suite con el modelo real y comparar.
5. `docs/CLAUDE-DESKTOP.md`: configuración para conectar el servidor a Claude Desktop (JSON de ejemplo). `README.md`
   en inglés con diagrama, qué evalúa cada métrica y por qué importa en producción.

Verificación (salida real): `pytest -q`, `ruff check .`, la suite con el LLM falso (reporte), y si Ollama está
disponible una corrida con el modelo real (pega la tabla; si no está, dilo).

Reglas: ponytail, sin commit ni push, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-18-A.md` (español) con la salida real de cada comando.
