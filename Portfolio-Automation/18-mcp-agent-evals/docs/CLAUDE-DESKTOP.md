# Conexión del Servidor MCP Sabor de Casa con Claude Desktop

Esta guía describe cómo integrar el servidor MCP de **Sabor de Casa** en **Claude Desktop** para habilitar herramientas en tiempo real de consulta de menú, horarios, creación de reservas validadas, estado de pedidos a domicilio y acceso a las políticas operativas del restaurante.

---

## 1. Ubicación del archivo de configuración

Edita o crea el archivo `claude_desktop_config.json` en la ruta correspondiente a tu sistema operativo:

- **Windows:**
  ```text
  %APPDATA%\Claude\claude_desktop_config.json
  (C:\Users\<usuario>\AppData\Roaming\Claude\claude_desktop_config.json)
  ```
- **macOS:**
  ```text
  ~/Library/Application Support/Claude/claude_desktop_config.json
  ```

---

## 2. Configuración vía Transporte Estándar (stdio)

El transporte `stdio` es el método recomendado para uso local con Claude Desktop. Ejecuta el servidor como un subproceso administrado mediante `uv`.

### Ejemplo para Windows:

```json
{
  "mcpServers": {
    "sabor-de-casa": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\valentina.alarcon\\Documents\\PER\\Cursos\\Claudia\\Portfolio Gemini\\Portfolio-Automation\\18-mcp-agent-evals",
        "run",
        "python",
        "-m",
        "app.server",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Ejemplo para macOS / Linux:

```json
{
  "mcpServers": {
    "sabor-de-casa": {
      "command": "uv",
      "args": [
        "--directory",
        "/ruta/a/Portfolio-Automation/18-mcp-agent-evals",
        "run",
        "python",
        "-m",
        "app.server",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 3. Configuración vía Transporte HTTP / SSE

Si prefieres ejecutar el servidor de forma independiente en segundo plano:

1. Inicia el servidor en una terminal:
   ```bash
   uv run python -m app.server --transport sse --host 127.0.0.1 --port 8000
   ```
2. Configura Claude Desktop con la URL del endpoint SSE:
   ```json
   {
     "mcpServers": {
       "sabor-de-casa-http": {
         "url": "http://127.0.0.1:8000/sse"
       }
     }
   }
   ```

---

## 4. Herramientas y Recursos Disponibles

Una vez configurado y reiniciado Claude Desktop, verás disponible el martillo de herramientas con:

| Herramienta | Parámetros | Descripción |
| :--- | :--- | :--- |
| `consultar_menu` | `categoria` (opcional), `plato` (opcional) | Precios en COP, ingredientes, alérgenos y disponibilidad. |
| `consultar_horario` | `dia` (opcional) | Horarios de martes a domingo (12m - 9pm), descanso de lunes y festivos. |
| `crear_reserva` | `nombre`, `telefono`, `fecha`, `hora`, `personas` | Valida franja horaria (12m - 8:30pm), máx. 12 personas, cupo (máx. 40). |
| `estado_pedido` | `id_pedido` (entero) | Consulta estado de preparación, ruta, items y dirección de entrega. |
| `zonas_domicilio` | `zona` (opcional) | Cobertura en Chapinero, Teusaquillo, Usaquén, Suba; pedido mín. $25.000. |

### Recurso MCP:
- **URI:** `politicas://sabor-de-casa/politicas`
- **Contenido:** Compendio unificado de políticas operativas extraídas de `13-whatsapp-restaurant-assistant/knowledge/`.

---

## 5. Ejemplos de Interacción en Claude Desktop

- *"¿Cuánto cuesta la Bandeja Paisa y qué alérgenos tiene?"*
- *"¿Tienen servicio los domingos por la noche?"*
- *"Quiero reservar una mesa para 4 personas el viernes 2026-11-20 a la 1:00 pm a nombre de Carlos Gomez, tel 3001234567."*
- *"¿Hacen envíos a Chapinero y cuánto demora?"*
- *"¿Cuál es el estado de mi pedido #1?"*
- *"Quiero reservar para 25 personas este sábado."* *(Claude responderá explicando el límite de 12 personas y ofreciendo el servicio de eventos/catering).*

---

## 6. Solución de Problemas

- **El servidor no aparece en Claude Desktop:**
  - Verifica que `uv` esté accesible en el PATH del sistema.
  - Asegúrate de reiniciar completamente Claude Desktop tras modificar `claude_desktop_config.json`.
  - Revisa los logs de Claude Desktop en `%APPDATA%\Claude\logs` (Windows) o `~/Library/Logs/Claude` (macOS).
- **Error de importación o rutas:**
  - Comprueba que la ruta `--directory` apunte exactamente a la carpeta `18-mcp-agent-evals`.
