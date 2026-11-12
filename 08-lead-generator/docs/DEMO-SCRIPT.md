# Demo Script (2 minutos) - 08 Lead Generator

**Objetivo:** Mostrar rápidamente cómo funciona el generador de leads de forma local, usando el directorio de demo preconfigurado.

## Paso 1: Levantar la Infraestructura (0:00 - 0:30)
*Acción:* Muestra la terminal e inicia Docker.
```bash
docker compose --env-file .env.example up -d --build --wait
```
*Narrativa:* "Aquí levantamos nuestro stack en Docker. Consta de la API (FastAPI), la base de datos (PostgreSQL) y un contenedor de Nginx que aloja un directorio simulado de 40 empresas. Esto hace que la demo sea 100% determinista y no dependa de internet."

## Paso 2: Ejecutar el trabajo desde la CLI (0:30 - 1:00)
*Acción:* Lanza una búsqueda a través del CLI.
```bash
python -m app.cli "restaurantes" "Bogotá" --out samples/leads-ejemplo.xlsx
```
*Narrativa:* "Al correr este comando, le ordenamos al sistema buscar 'restaurantes' en 'Bogotá'. En el fondo, el pipeline extrae los registros, normaliza textos y teléfonos, valida los correos y fusiona duplicados: dos leads se unen si sus nombres se parecen más de un 85 % (`rapidfuzz`) y además comparten teléfono o dominio web."

## Paso 3: Visualizar los resultados en Excel (1:00 - 1:45)
*Acción:* Abre el archivo generado `samples/leads-ejemplo.xlsx`.
*Narrativa:* "Este es el entregable final. Como pueden ver:
- En la hoja **Leads**, tenemos un formato condicional para visualizar rápidamente qué tan completo es cada lead, además de enlaces cliqueables.
- En la hoja **Resumen**, vemos la distribución por categorías.
- En la hoja **Fuentes**, podemos auditar cuántos registros vinieron de cada fuente y cuántos duplicados fueron fusionados para darnos una lista limpia."

## Paso 4: Apagar el sistema (1:45 - 2:00)
*Acción:* Limpia el entorno para liberar memoria.
```bash
docker compose --env-file .env.example stop
```
*Narrativa:* "Todo el orquestado de trabajos corre en tareas de fondo (`BackgroundTasks`) de FastAPI, lo que elimina la necesidad de infraestructuras pesadas como Redis o Celery, manteniendo el costo operativo y la complejidad al mínimo. Gracias."
