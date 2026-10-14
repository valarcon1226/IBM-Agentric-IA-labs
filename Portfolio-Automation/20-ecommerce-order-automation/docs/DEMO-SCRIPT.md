# Guión de Demostración (Demo Script) - 5 Minutos

Este guión está diseñado para presentar el producto a clientes y dueños de e-commerce en una reunión en vivo de 5 minutos, demostrando el valor de la automatización centralizada de pedidos.

---

## ⏱️ Minuto 0:00 - 1:00 · El Problema que Resolvemos
> **Discurso:**
> *"Actualmente la mayoría de marcas de café de especialidad y tiendas online venden por múltiples canales: su propia tienda WooCommerce o Shopify, pasarelas de pago como Stripe o links directos. El dolor de cabeza diario es que el equipo de bodega tiene que entrar a 3 paneles distintos, revisar correos de confirmación manuales, copiar y pegar direcciones de entrega en hojas de cálculo y avisarle al cliente por WhatsApp de uno en uno. Esto genera errores de despacho, demoras y pérdida de tiempo.
>
> Hoy les presento la solución centralizada para 'Café de Origen': un sistema que unifica todos los pedidos de cualquier plataforma en tiempo real, verifica las firmas de seguridad para evitar fraudes, notifica al cliente automáticamente y le da al equipo de bodega un panel único y accesible desde el celular."*

---

## ⏱️ Minuto 1:00 - 2:30 · Demostración en Vivo: Ingesta Multicanal
1. **Mostrar el estado inicial del panel:**
   - Abre `http://localhost:8000/admin` en el navegador.
   - Inicia sesión con el usuario `admin` y contraseña segura.
   - Muestra las tarjetas de métricas en ceros o con pedidos previos.

2. **Ejecutar el simulador de webhooks:**
   - Abre la terminal y ejecuta:
     ```bash
     python samples/send_webhooks.py
     ```
   - Señala en pantalla lo que ocurre en milisegundos:
     - **Canal 1:** Llega un pedido de **WooCommerce** (Valentina Alarcón, Bogotá, $86.000 COP).
     - **Canal 2:** Llega un pedido de **Shopify** (Carlos Mendoza, Medellín, $55.000 COP).
     - **Canal 3:** Llega un pago con tarjeta confirmado por **Stripe** (Andrea Gómez, Medellín, $84.000 COP).

3. **Demostrar la Idempotencia y Seguridad:**
   - Resalta el paso [4/5] del script: el mismo pedido de WooCommerce se envió por error de red una segunda vez. El sistema lo reconoció al instante como duplicado (`duplicate_event`) y lo descartó sin duplicar inventario ni cobros.
   - Resalta el paso [5/5]: un intento de inyección con firma digital falsa fue rechazado automáticamente con código `401 Unauthorized`.

---

## ⏱️ Minuto 2:30 - 3:30 · Notificaciones Inmediatas (Email y WhatsApp)
1. **Bandeja de Correo (Mailpit):**
   - Abre `http://localhost:8025`.
   - Muestra cómo los 3 clientes recibieron al instante su correo electrónico de confirmación con diseño profesional de Café de Origen, detalle de productos y estado *"Listo para Despachar"*.
2. **Notificación de WhatsApp:**
   - Muestra en el log de la aplicación la notificación estructurada generada para el mensajero y el cliente con el formato oficial de WhatsApp Cloud API.

---

## ⏱️ Minuto 3:30 - 4:30 · Gestión de Bodega y Despacho desde el Celular
1. **Actualizar la vista de pedidos:**
   - Regresa a `http://localhost:8000/admin/orders`.
   - Muestra cómo los pedidos de los 3 canales ya están consolidados, con sus etiquetas de plataforma (`woocommerce`, `shopify`, `stripe`) y su estado inicial `listo para despachar`.
2. **Entrar al detalle de un pedido:**
   - Haz clic en *"Ver / Gestionar"* del pedido `ORD-WC-501`.
   - Explica la trazabilidad y la dirección de entrega.
   - Cambia el estado a **"Despachado"** ingresando el número de guía (ej. `Coordinadora #889211`).
   - Haz clic en guardar: muestra cómo se actualiza la línea de tiempo y se envía el aviso automático al cliente.
3. **Descarga de Reporte a Excel:**
   - Haz clic en el botón superior **"Exportar a Excel (.xlsx)"**.
   - Abre el archivo descargado para mostrar las columnas limpias listas para el transportador o contabilidad.

---

## ⏱️ Minuto 4:30 - 5:00 · Cierre y Propuesta de Valor
> **Discurso:**
> *"Con esta solución, el negocio ahorra más de 20 horas a la semana en trabajo manual de logística, elimina el 100% de los pedidos duplicados o traspapelados y brinda una experiencia de marca de primer nivel a cada comprador.
> La arquitectura está lista para desplegarse en servidor propio o en la nube con Docker Compose en menos de 10 minutos."*
