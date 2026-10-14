# Guía de Creación de Cuentas Gratuitas de Prueba (Shopify Partners y Stripe)

Esta guía explica paso a paso cómo la propietaria de la tienda puede crear sus entornos de desarrollo y prueba oficiales sin costo alguno y **sin necesidad de ingresar tarjetas de crédito ni datos bancarios**.

---

## 1. Tienda de Desarrollo en Shopify Partners (Gratis y sin límite de tiempo)

Shopify ofrece a agencias y desarrolladores la plataforma **Shopify Partners**, que permite crear tiendas de prueba con funcionalidad completa (catálogo, checkout, webhooks y API) de forma indefinida sin pagar ninguna suscripción.

### Paso a paso:
1. **Registro en Shopify Partners:**
   - Ingresa a [https://www.shopify.com/partners](https://www.shopify.com/partners).
   - Haz clic en **"Únete ahora"** (Join now).
   - Regístrate con tu correo electrónico empresarial o personal (ej. `contacto@cafedeorigen.co`).
   - Completa el perfil con el nombre de tu marca: "Café de Origen".

2. **Crear una Tienda de Desarrollo:**
   - En el panel de control de Partners, ve al menú lateral izquierdo y selecciona **Tiendas (Stores)**.
   - Haz clic en el botón superior **"Añadir tienda" (Add store)** y selecciona **"Crear tienda de desarrollo" (Create development store)**.
   - Selecciona el propósito: **"Crear una tienda para probar o desarrollar apps"**.
   - Asigna un nombre a la tienda: `cafe-de-origen-demo`.
   - Selecciona **"Empezar con datos de prueba"** (opcional, para tener clientes y productos precargados).
   - Haz clic en **"Crear tienda de desarrollo"**.

3. **Configurar el Webhook de Pedidos (`orders/create`):**
   - Dentro del panel de administración de la tienda (`https://admin.shopify.com/store/cafe-de-origen-demo`):
   - Ve a **Configuración (Settings)** &rarr; **Notificaciones (Notifications)**.
   - Baja hasta la sección **Webhooks**.
   - Haz clic en **"Crear webhook"**:
     - **Evento:** `Creación de pedido (Order creation)`.
     - **Formato:** `JSON`.
     - **URL:** `https://tu-dominio-o-ngrok.com/webhooks/shopify` (o la IP pública del servidor).
     - **Versión de la API de Webhook:** La más reciente recomendada (ej. `2024-10` o `2025-01`).
   - Copia la **Clave secreta de firma de webhook** que aparece en el recuadro inferior y colócala en tu `.env` como `SHOPIFY_WEBHOOK_SECRET`.

---

## 2. Cuenta de Stripe en Modo Prueba (Test Mode sin tarjeta)

Stripe permite registrarse y utilizar el 100% de su API de pagos, Payment Intents y webhooks en modo simulación sin proporcionar información bancaria.

### Paso a paso:
1. **Crear cuenta en Stripe:**
   - Ingresa a [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register).
   - Introduce tu email, nombre y contraseña.
   - Confirma el correo electrónico que Stripe te enviará.
   - **Nota:** Si Stripe solicita "Activar cuenta" con datos fiscales o cuenta bancaria, **omite ese paso**. El modo de prueba está disponible de inmediato sin activación.

2. **Activar el Modo de Prueba:**
   - En la esquina superior derecha del Dashboard de Stripe, asegúrate de que el selector **"Modo de prueba" (Test mode)** esté activado (interruptor en color naranja/morado).

3. **Obtener las Claves de API:**
   - Ve a **Desarrolladores (Developers)** &rarr; **Claves de API (API keys)**.
   - Obtendrás:
     - Clave publicable de prueba: `pk_test_...`
     - Clave secreta de prueba: `sk_test_...`

4. **Configurar el Endpoint de Webhooks:**
   - En el menú **Desarrolladores**, haz clic en **Webhooks**.
   - Haz clic en **"Añadir un endpoint" (Add destination)**.
   - **URL del endpoint:** `https://tu-dominio-o-ngrok.com/webhooks/stripe`.
   - **Eventos para escuchar:**
     - Haz clic en "Seleccionar eventos".
     - Marca `payment_intent.succeeded` y opcionalmente `checkout.session.completed`.
   - Haz clic en **"Añadir endpoint"**.
   - En la página de detalles del webhook recién creado, haz clic en **"Revelar"** en la sección **Secreto de firma**.
   - Copia la clave secreta (empieza con `whsec_...`) y colócala en tu `.env` como `STRIPE_WEBHOOK_SECRET`.

---

## 3. Pruebas Locales con Stripe CLI o ngrok

Para recibir webhooks en tu máquina local sin abrir puertos en el router:

- **Con Stripe CLI:**
  ```bash
  stripe login
  stripe listen --forward-to localhost:8000/webhooks/stripe
  ```
  Stripe CLI te imprimirá un secreto de webhook específico para pruebas locales (`whsec_...`).

- **Con ngrok:**
  ```bash
  ngrok http 8000
  ```
  Copia la URL HTTPS generada (ej. `https://xyz.ngrok-free.app`) y úsala en los paneles de WooCommerce, Shopify y Stripe.
