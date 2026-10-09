# Demo Script del Chat Web

Para mostrar a los clientes el funcionamiento del widget de Sabor de Casa:

1. **Abre el Demo Local**:
   - Corre el servidor del Proyecto 13 (`uv run fastapi dev app/main.py`).
   - Visita `http://127.0.0.1:8000/widget/demo/index.html`.

2. **Interacción de prueba**:
   - Da clic en el botón flotante.
   - Escribe: `¿Qué platos principales tienen?`
   - Espera la respuesta (verás "Escribiendo...").
   - El bot responderá con la lista, incluyendo el Ajiaco y la Bandeja Paisa.

3. **Reserva (Demo)**:
   - Escribe: `Quiero reservar para mañana a las 7pm para 2 personas.`
   - El bot creará la reserva y mostrará el identificador.

4. **Navegación por teclado**:
   - Usa `Tab` para enfocar, `Enter` para abrir y cerrar el chat, y la tecla `Escape` desde el área de texto para cerrar el panel.
