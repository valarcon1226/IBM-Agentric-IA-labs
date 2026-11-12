# Guion de demo (2 minutos) — Sabor de Casa

Demo corta mostrando los 4 flujos en la interfaz de n8n (http://localhost:5680, pestaña
**Executions** de cada flujo) y los correos "enviados" en mailpit (http://localhost:8027).

Antes de empezar: stack levantado y saludable.

```powershell
docker compose --env-file .env.example up -d --build --wait
docker compose ps
```

## Minuto 0:00 – 0:30 — F1: un lead nuevo llega del formulario de la web

```powershell
curl -X POST http://localhost:5680/webhook/lead-form `
  -H "X-Api-Key: change_me_webhook_api_key" -H "Content-Type: application/json" `
  -d '{"name":"Ana Gomez","email":"ana.demo@example.com","phone":"3001234567","event_type":"matrimonio","event_date":"2026-12-05","guests":60,"message":"Queremos cotizar el salón grande"}'
```

**Qué mostrar:** la respuesta `{"status":"created","lead_id":...}`, la ejecución verde en n8n, y
en mailpit el correo de bienvenida a `ana.demo@example.com`. Repetir el mismo `curl` una segunda
vez para mostrar que detecta el lead repetido (`"status":"duplicate"`) y no manda un segundo
correo.

## Minuto 0:30 – 1:00 — F2: llega una factura de un proveedor

```powershell
curl -X POST http://localhost:5680/webhook/invoice-upload `
  -H "X-Api-Key: change_me_webhook_api_key" -H "Content-Type: application/pdf" `
  --data-binary "@samples/factura-valida.pdf"
```

**Qué mostrar:** la IA (`fake-llm` en local, un proveedor real en producción) leyó el PDF y
extrajo proveedor/NIT/fecha/subtotal/IVA/total/ítems; la factura quedó guardada con
`status: validated`. Ahora la que no cuadra:

```powershell
curl -X POST http://localhost:5680/webhook/invoice-upload `
  -H "X-Api-Key: change_me_webhook_api_key" -H "Content-Type: application/pdf" `
  --data-binary "@samples/factura-totales-no-cuadran.pdf"
```

**Qué mostrar:** `"status":"needs_review"` con el motivo exacto (`total does not match subtotal +
iva`), la fila en la base queda marcada para revisión en vez de guardarse con un dato incorrecto,
y le llega un correo al equipo pidiendo revisarla a mano.

## Minuto 1:00 – 1:30 — F3: el reporte diario de ventas

```powershell
curl -X POST http://localhost:5680/webhook/daily-report-trigger `
  -H "X-Api-Key: change_me_webhook_api_key" -H "Content-Type: application/json" `
  -d '{"date":"2025-01-15"}'
```

**Qué mostrar:** este es el mismo flujo que corre solo todos los días a las 7:00 a.m. (hora
Colombia, siempre sobre las ventas de "ayer") — aquí lo disparamos a mano para la demo, pidiendo
explícitamente la fecha fija de ejemplo `2025-01-15` (datos sembrados en `init-db.sql`, para que
la demo muestre ventas reales sin importar qué día se corra). La respuesta trae el total de ese
día; en mailpit llega el resumen en español escrito por la IA repitiendo los platos y montos
reales de la tabla `sales`. Si se llama sin `date` en el cuerpo, usa "ayer" (igual que el cron de
las 7 a.m.) — en una base recién creada eso normalmente da "sin ventas", porque el seed de
ejemplo está fijado en el pasado, no en la fecha real de ayer.

## Minuto 1:30 – 2:00 — F4: confirmación de un pago

Necesita la firma HMAC del "proveedor de pagos" (se calcula con el mismo secreto que
`PAYMENT_WEBHOOK_SECRET` en `.env.example`):

```powershell
$body = '{"id":"evt_demo_001","type":"payment.succeeded","data":{"order_id":3,"amount_cop":96000}}'
$secret = "change_me_payment_webhook_secret"
$hmac = New-Object System.Security.Cryptography.HMACSHA256([System.Text.Encoding]::UTF8.GetBytes($secret))
$sig = [System.BitConverter]::ToString($hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($body))).Replace("-","").ToLower()
curl -X POST http://localhost:5680/webhook/payment-webhook -H "X-Signature: sha256=$sig" -H "Content-Type: application/json" -d $body
```

**Qué mostrar:** el pedido #3 (uno de los pendientes de la data de ejemplo) pasa a `paid`, el
cliente recibe confirmación por correo, y al equipo le llega el aviso. Repetir el mismo `curl`
(mismo `id` de evento) para mostrar que el reintento no duplica nada (`"status":"ignored"`).

---

**Nota para quien presente:** todos los webhooks de entrada exigen `X-Api-Key` salvo F4, que
exige la firma HMAC en su lugar — quitar el header en cualquiera de los `curl` anteriores muestra
el rechazo (`403` o `401`) sin que nada se guarde.
