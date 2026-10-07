# 22-A · Chat web con IA y acciones para Sabor de Casa (embebible)

Carpeta nueva: `Portfolio-Automation/22-web-chat-widget`. Además puedes tocar SOLO lo necesario de
`13-whatsapp-restaurant-assistant` para agregar un canal web. Imita gigs de "AI chatbot for website with RAG and
function calling" (el tipo de gig #1 en jobHunter, 71 gigs).

1. Lee completo el 13 (`app/agent.py`, `tools.py`, `retrieval.py`, `dev_chat.py`). NO dupliques el cerebro: agrega en el
   13 un router `app/web_chat.py` con `POST /web/chat` (sesión por id, CORS solo para orígenes de `.env`, límite de
   tamaño y de mensajes por minuto) que usa el mismo agente y herramientas que WhatsApp. Sus tests en el 13.
2. En el 22: `widget.js` sin dependencias que se pega con
   `<script src=".../widget.js" data-api="..." data-title="..."></script>`: botón flotante, panel de chat, historial
   de la sesión, indicador de escritura, mensajes de error claros. Accesible: navegable con teclado, `aria-live`
   para las respuestas, foco correcto al abrir/cerrar, contraste AA, funciona en celular.
3. Acciones que debe mostrar el demo (las herramientas que ya tenga el 13; si falta alguna, agrégala allí):
   consultar menú y precios, crear una reserva, consultar zonas de domicilio, dejar datos para que lo llamen.
4. Panel `/admin` (protegido con API key de `.env`) para subir un PDF o .md a la base de conocimiento del 13 y
   reindexar. Valida tipo y tamaño del archivo.
5. Página `demo/index.html` que embebe el widget, y un snippet para pegarlo en el WordPress del 16
   (`docs/WORDPRESS.md`: dónde pegarlo, sin plugins).
6. Pruebas Playwright (en el 22): abre el widget, pregunta por el menú, crea una reserva, navega solo con teclado.
   Con el LLM falso del 13. `README.md` en español para clientes + `docs/DEMO-SCRIPT.md` (guion del video de 1 min).

Verificación (salida real): tests del 13 (`pytest -q`), Playwright del 22, `docker compose up` del 13 + demo
funcionando (captura en `docs/`), y al final `docker compose stop`.

Reglas: ponytail, sin commit ni push, sin `.env` reales, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-22-A.md` (español) con la salida real de cada comando.
