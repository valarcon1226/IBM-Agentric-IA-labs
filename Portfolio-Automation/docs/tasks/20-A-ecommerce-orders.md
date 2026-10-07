# 20-A · Automatización de pedidos e-commerce: WooCommerce + Shopify + Stripe + MongoDB

Carpeta nueva: `Portfolio-Automation/20-ecommerce-order-automation` (solo esta). Imita gigs bien pagados de "order
fulfillment automation", "Shopify API", "secure payment integrations", "MongoDB" y "producto completo con login y panel".
Tienda ficticia: "Café de Origen" (café colombiano; 8–10 productos de ejemplo marcados como ficticios).

1. FastAPI + MongoDB (contenedor `mongo` con versión fija, sin Atlas). Modelos: producto, cliente, pedido, evento.
2. Webhooks con **firma verificada** y rechazo si no coincide: WooCommerce (`order.created`, HMAC-SHA256 base64),
   Shopify (`orders/create`, `X-Shopify-Hmac-Sha256`), Stripe (`payment_intent.succeeded`, `Stripe-Signature` con
   tolerancia de tiempo; usa la librería oficial). Idempotencia: el mismo evento dos veces no duplica nada.
3. Todos los pedidos se normalizan a un solo formato. Al pagarse: estado "listo para despachar", email al cliente
   (SMTP a `mailpit` en el compose) y notificación de WhatsApp detrás de una interfaz (en el demo, un stub que escribe
   en el log; documenta cómo conectar la Cloud API como en el 13).
4. Panel `/admin` con login (contraseñas con hash, sesión con cookie segura, protección CSRF, bloqueo tras intentos
   fallidos): lista de pedidos con filtros, cambiar estado (pagado → despachado → entregado, cada cambio avisa al
   cliente), exportar a Excel. Accesible y usable en celular.
5. `samples/`: payloads de ejemplo de los 3 webhooks y un script que los firma y los envía (para el demo sin cuentas).
6. Tests pytest: firma válida/ inválida/vencida de cada plataforma, idempotencia, cambios de estado, login y CSRF,
   exportación. `docker-compose.yml` (api, mongo, mailpit) con healthchecks.
7. `README.md` en español para clientes + `docs/DEMO-SCRIPT.md`. En `docs/CUENTAS.md` los pasos para que la dueña cree
   gratis la tienda de desarrollo de Shopify Partners y la cuenta de Stripe en modo prueba (sin tarjeta) — eso es del
   lote B, aquí solo la guía.

Verificación (salida real): `pytest -q`, `ruff check .`, `docker compose up -d --build`, el script de `samples/`
enviando los 3 webhooks y el pedido resultante en el panel (captura en `docs/`), email en mailpit, `docker compose down`.

Reglas: ponytail, sin commit ni push, sin `.env` reales (solo `.env.example` con `change_me_<nombre>`), sin secretos,
no toques otras carpetas. Al terminar escribe `docs/reviews/T-20-A.md` (español) con la salida real de cada comando.
