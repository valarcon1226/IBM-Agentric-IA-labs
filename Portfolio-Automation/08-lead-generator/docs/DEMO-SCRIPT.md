# Demo Script (2 minutos)

1. **Levantar el entorno local (si no está arriba)**
   ```bash
   docker compose --env-file .env.example up -d --build --wait
   ```
   > Esto levanta la API, la base de datos PostgreSQL, y el directorio de demostración.

2. **Lanzar un trabajo de generación de leads**
   Usaremos el CLI que internamente consume el mismo pipeline:
   ```bash
   python -m app.cli "restaurantes" "Bogotá" --out leads.xlsx
   ```
   > (Opcional) Muestra en los logs de la API cómo se visita el directorio, se extraen perfiles, se visita cada página individual, y finalmente cómo se consolidan los duplicados (ej. restaurantes que se escriben distinto).

3. **Revisar el Excel generado (`leads.xlsx`)**
   - Abre el archivo `leads.xlsx`
   - Muestra la hoja **"Leads"**, destaca:
     - El puntaje de calidad con colores.
     - La consolidación de información (deduplicación).
     - La validación del email y teléfono normalizado.
   - Muestra la hoja **"Resumen"** y **"Fuentes"** para observar métricas básicas.

4. **Apagar el entorno**
   ```bash
   docker compose --env-file .env.example stop
   ```
   > Apagamos para liberar memoria local, mostrando lo fácil que es controlar la infraestructura.
