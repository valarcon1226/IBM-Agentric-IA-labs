# Guion de demo (2 minutos) — Sabor de Casa

Demo corta con `scripts/chat.py` (modo desarrollo, sin necesitar WhatsApp real) o, si ya está
conectado, directamente desde WhatsApp. Pensada para mostrar las tres líneas de negocio y el
traspaso a una persona.

Antes de empezar: stack levantado (`docker compose --env-file .env up -d`) y, si usas el chat de
terminal, `python scripts/chat.py 573001112233` corriendo en una ventana.

## Minuto 0:00 – 0:30 — Pedido a domicilio

**Cliente:**
> Hola, quiero pedir una bandeja paisa y una limonada de coco para la Calle 10 #5-20 en
> Chapinero, pago contraentrega

**Qué mostrar:** el bot reconoce los platos, calcula el subtotal, agrega el domicilio de la zona
y confirma el pedido con un número. Resaltar que el total **lo calcula el servidor**, no el
cliente ni el LLM.

## Minuto 0:30 – 1:00 — Reserva de mesa

**Cliente:**
> Quiero reservar mesa para 4 personas mañana a las 7pm

**Qué mostrar:** el bot valida el horario y el día (si cae lunes, lo rechaza y lo explica), revisa
cupo disponible y confirma la reserva. Mencionar que un día antes llega un recordatorio
automático por WhatsApp.

## Minuto 1:00 – 1:30 — Evento grande → traspaso a humano

**Cliente:**
> Necesito cotizar un matrimonio para 80 personas el 15 de diciembre, presupuesto 8 millones,
> mi nombre es Juan Pérez

**Qué mostrar:** el bot reconoce que es un grupo grande (> 12 personas), pide los datos clave y
registra la oportunidad para el equipo comercial — no intenta cerrar la cotización él solo.

**Cliente:**
> Prefiero hablar con alguien para cerrar los detalles

**Qué mostrar:** el bot hace el traspaso: queda en silencio con este cliente, y en paralelo en la
ventana/número de staff llega una notificación con el motivo, el número (enmascarado) y un
resumen corto.

## Minuto 1:30 – 2:00 — Respuesta del staff

Desde el número de staff (uno de los listados en `STAFF_WA_IDS`):

**Staff:**
> /pedidos

**Qué mostrar:** lista de pedidos pendientes del día.

**Staff:**
> /r 573001112233 Hola Juan, soy Andrea del restaurante, hablemos de los detalles del evento

**Qué mostrar:** el mensaje llega directo al cliente sin pasar por el bot. Cerrar mostrando
`/bot 573001112233` para devolverle el control al bot cuando la conversación humana termine.

---

**Nota para quien presente:** si se usa `scripts/chat.py` en modo `LLM_FAKE=true` para una demo
sin dependencias externas, el "mensaje del cliente" debe escribirse como el JSON de la
herramienta (p. ej. `{"tool": "create_order", "arguments": {...}}`) en vez de lenguaje natural —
ver la sección 5 del README para el detalle.
