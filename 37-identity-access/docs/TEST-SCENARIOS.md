# Escenarios de Prueba de Recuperación de Credenciales — `TEST-SCENARIOS.md`

Este documento registra los escenarios interactivos de recuperación de credenciales y restablecimiento de contraseña (`tests/ui/test_password_reset.py`), modelados en OWASP ASVS v4.0.3 Capítulo V2 (V2.5, V2.8) y trazados al requerimiento `REQ-IAM-004`.

---

## Escenario 1: Flujo Normal de Restablecimiento de Contraseña (Happy Path)

1. **Paso 1: Solicitud inicial en interfaz de usuario**
   - URL: `/realms/identity-realm/login-actions/reset-credentials?client_id=account-console`
   - Acción: El usuario introduce su nombre de usuario (`bench_user_00070`) y envía el formulario.
   - **Mensaje visible en pantalla (User-facing):**
     > *"You should receive an email shortly with further instructions."*

2. **Paso 2: Notificación por Correo Electrónico (Mailpit API)**
   - Asunto: `Reset password`
   - Remitente: `noreply@identity.local`
   - Enlace de acción generado:
     `http://127.0.0.1:8081/realms/identity-realm/login-actions/action-token?key=<JWT_ACTION_TOKEN>&execution=...`

3. **Paso 3: Actualización de Contraseña**
   - El usuario abre el enlace de restablecimiento.
   - Interfaz: Formulario con campos `#password-new` y `#password-confirm`.
   - Acción: El usuario establece su nueva contraseña (`UpdatedPassword123!`) y confirma.

4. **Paso 4: Autenticación con la Nueva Credencial**
   - El usuario inicia sesión en `/realms/identity-realm/account` con la nueva contraseña.
   - Resultado: Acceso concedido exitosamente a la consola de cuenta.

---

## Escenario 2: Reutilización de Enlace Usado (Replay Attack Prevention)

- **Vector de Amenaza:** Un atacante intercepta un enlace de restablecimiento o un usuario reintenta usar el mismo enlace ya consumido.
- **Acción:** Navegación por segunda vez a la URL del token de acción previamente canjeado.
- **Título en Pantalla:** `We are sorry...`
- **Mensaje visible en pantalla (User-facing):**
  > *"Action expired. Please continue with login now."*
- **Comprobación de Seguridad:**
  - El formulario de cambio de contraseña (`#password-new`) **no se renderiza**.
  - La sesión anterior no se restaura.

---

## Escenario 3: Expiración de Enlace por Tiempo (Token Lifetime Expiry)

- **Configuración de Prueba:** `actionTokenGeneratedByUserLifespan = 3` segundos.
- **Vector de Amenaza:** Uso de un enlace de recuperación fuera de la ventana de validez temporal.
- **Acción:** El usuario espera a que transcurra el tiempo de vida (3,5 segundos) y accede al enlace.
- **Título en Pantalla:** `Sign in to your account`
- **Mensaje visible en pantalla (User-facing):**
  > *"Action expired. Please start again."*
- **Comprobación de Seguridad:**
  - El token es revocado criptográficamente por expiración de claim `exp`.
  - El usuario es redirigido a la página de login general.

---

## Escenario 4: Caída de Infraestructura SMTP (Toxiproxy Fault Injection)

- **Inyección de Falla:** Toxiproxy deshabilita el proxy TCP del servidor SMTP (`POST /proxies/smtp {"enabled": false}`).
- **Acción del Usuario:** Solicitud de restablecimiento de contraseña para un usuario existente (`bench_user_00072`).
- **Título en Pantalla:** `We are sorry...`
- **Mensaje visible en pantalla (User-facing):**
  > *"Failed to send email, please try again later."*
- **Verificación Anti-Enumeración (ASVS V2.5.4):**
  - La respuesta **no revela si la cuenta existe o no**.
  - El nombre de usuario y la dirección de correo electrónico solicitada **no se reflejan** en el DOM ni en los encabezados.
  - El servidor de correo (Mailpit) registra **0 mensajes** entregados durante la caída.

---

## Escenario 5: Recuperación y Reintento tras Restauración SMTP

- **Restauración del Servicio:** Toxiproxy rehabilita el enlace TCP hacia Mailpit (`{"enabled": true}`).
- **Acción del Usuario:** Reintento de solicitud de restablecimiento para el mismo usuario.
- **Resultado:**
  - En pantalla: *"You should receive an email shortly with further instructions."*
  - En Mailpit: Se entrega **exactamente 1 correo electrónico utilizable**.
  - El enlace recuperado permite actualizar la contraseña satisfactoriamente.
