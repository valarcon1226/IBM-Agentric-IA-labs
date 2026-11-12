# Web Chat Widget

Este es el widget de chat web para Sabor de Casa, que se conecta directamente al asistente virtual (Proyecto 13).

## ¿Qué hace?
Muestra un botón flotante en cualquier sitio web que, al hacer clic, abre un panel de chat. Los mensajes enviados por el usuario se comunican con el servidor FastAPI para obtener respuestas usando LLMs, consultar el menú, o crear reservas.

## ¿Cómo pegarlo en cualquier web?
Solo necesitas incluir este script justo antes de cerrar tu etiqueta `</body>`, asegurándote de configurar los atributos `data-api` y `data-title`:

```html
<script src="https://tu-servidor.com/widget.js" 
        data-api="https://tu-api.com" 
        data-title="Asistente Sabor de Casa"></script>
```

## ¿Cómo levantarlo?
El widget puede ser servido por cualquier servidor estático o puede consumirse directamente desde el mismo backend de FastAPI, que ya lo sirve en la ruta `/widget`.

## Seguridad
- **CORS**: Asegúrate de que `WEB_CORS_ORIGINS` en el proyecto 13 incluye el dominio donde se hospeda la web para permitir las solicitudes.
- **API Key**: Las interacciones de chat no requieren llave, pero el panel de administración (`/admin`) requiere `ADMIN_API_KEY`.
- **Límite de tasa**: Se encuentra protegido con el mismo sistema que WhatsApp (rate limit de mensajes recientes).

## Capturas
El chat aparecerá en la esquina inferior derecha. Un botón circular negro y un panel blanco de diseño responsivo.
