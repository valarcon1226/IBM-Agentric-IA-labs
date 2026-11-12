# Sitio Web Sabor de Casa

Sitio web completo para el restaurante "Sabor de Casa", construido con WordPress y Docker.

## Qué incluye

*   **Páginas**: Inicio, Menú, Reservas, Domicilios, Eventos y Catering, Contacto, Política de Privacidad.
*   **Reservas online**: Integración de reservas en tiempo real con confirmación por correo electrónico.
*   **Formularios de contacto**: Formularios para eventos y catering.
*   **SEO Local**: Marcado JSON-LD con Schema.org y Open Graph.
*   **Integración WhatsApp**: Botón flotante para chat directo.
*   **Performance**: Imágenes optimizadas en WebP y configuración de rendimiento.

## Requisitos

*   Docker y Docker Compose
*   Node.js (para pruebas e informes)

## Cómo levantarlo paso a paso

1. Clonar el repositorio y acceder a la carpeta:
   ```bash
   cd 16-restaurant-website
   ```
2. Iniciar los contenedores:
   ```bash
   docker compose up -d
   ```
3. Ejecutar el script de configuración inicial (instala WordPress, plugins, y carga los contenidos):
   ```bash
   docker compose exec wp-cli bash /scripts/setup.sh
   ```
4. Acceder al sitio en: `http://localhost:8016`
5. El panel de administración (wp-admin) estará en `http://localhost:8016/wp-admin`
6. Los correos (reservas/contactos) se pueden ver en Mailpit: `http://localhost:8025`

## Cómo correr pruebas y Lighthouse

*   **Pruebas End-to-End**:
    ```bash
    npm install
    npx playwright test
    ```
*   **Lighthouse**:
    ```bash
    npx lighthouse http://localhost:8016 --view
    ```

## Cómo publicarlo en un hosting

1. Adquirir un dominio y hosting compatible con Docker o VPS.
2. Transferir los archivos `docker-compose.yml` y `.env` al servidor.
3. Actualizar los valores en `.env` (credenciales seguras) y `WP_URL` con el dominio real.
4. Levantar con `docker compose up -d` y configurar un proxy inverso (como Nginx o Traefik) con certificados SSL.
5. Ejecutar la configuración inicial si es la primera vez.

## Puntajes actuales (Lighthouse)

Última medición local (página de inicio, `lighthouse-report.json`):

*   Performance: 81
*   Accessibility: 95
*   Best Practices: 100
*   SEO: 92

Rendimiento es lo que falta mejorar: caché de página y carga diferida de imágenes y scripts que no se ven al inicio.

## Decisiones técnicas

*   **Plugin de Reservas**: Se decidió reemplazar el plugin `restaurant-reservations` por un Custom Post Type (`rtb-booking` interno para compatibilidad) y un shortcode en el mu-plugin `sabor-custom.php`. Esto permite que en un montaje 100% limpio (desde cero con `setup.sh`) el formulario se genere y configure de forma totalmente confiable, enviando directamente los correos a Mailpit sin depender del asistente de configuración que exigen algunos plugins.
