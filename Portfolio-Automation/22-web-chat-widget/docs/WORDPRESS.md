# Integración con WordPress

Para embeber este widget de chat en el sitio WordPress creado en el proyecto 16, sigue estos pasos:

1. **Sube el archivo JS (Opcional)**: 
   Puedes servir `widget.js` en tu servidor de FastAPI o puedes subir el script `widget.js` a la biblioteca de medios de WordPress o tu propio servidor estático.

2. **Incrustar en el footer de WordPress**:
   Para que el widget aparezca en todas las páginas, la mejor opción es usar un plugin como "Insert Headers and Footers" (ahora WPCode), o editar directamente el `footer.php` de tu tema hijo.

3. **Agrega el script**:
   Inserta el siguiente código justo antes de la etiqueta `</body>`:
   ```html
   <script src="https://TU-URL-DEL-PROYECTO-13/widget/widget.js" 
           data-api="https://TU-URL-DEL-PROYECTO-13" 
           data-title="Asistente Sabor de Casa"></script>
   ```

4. **Configura CORS en el backend**:
   Asegúrate de que la URL de tu sitio de WordPress está listada en la variable `WEB_CORS_ORIGINS` del archivo `.env` del Proyecto 13, por ejemplo:
   `WEB_CORS_ORIGINS=https://misitio-wordpress.com`

5. **Verifica**:
   Recarga la página de WordPress y deberías ver el botón del chat en la esquina inferior derecha.
