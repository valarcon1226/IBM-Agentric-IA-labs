# Generador de Leads B2B (B2B Lead Generator)

## 1. El Problema

Los equipos de ventas y marketing invierten innumerables horas buscando manualmente en directorios de empresas y sitios web para encontrar clientes B2B potenciales. Los datos suelen estar duplicados, desestructurados o carecer de información de contacto vital.

Este sistema automatiza la generación de leads B2B de alta calidad. Extrae información de directorios y sitios de forma concurrente, elimina duplicados automáticamente, enriquece los datos (validación de correos electrónicos, normalización de teléfonos a E.164) y los puntúa según qué tan completos estén. El resultado final es una lista estructurada, limpia y procesable, ideal para campañas de ventas (outbound), entregable en un archivo Excel.

## 2. ¿Qué recibe el cliente?

Como resultado de un trabajo de búsqueda, obtendrás un archivo de Excel (`.xlsx`) completamente funcional con tres hojas:
- **Leads:** La lista de empresas con sus datos de contacto limpios y validados, filtrable y con formatos condicionales.
- **Resumen:** Estadísticas generales de los leads encontrados (por categoría y rango de puntuación).
- **Fuentes:** El detalle de cuántos datos provino de cada fuente y cuántos duplicados fueron fusionados.

![Ejemplo de Excel](/samples/leads-ejemplo.xlsx)  
*(Captura de pantalla placeholder del archivo Excel generado).*

## 3. Uso del CLI (Línea de Comandos)

Puedes lanzar trabajos de extracción directamente desde tu terminal:
```bash
python -m app.cli "restaurantes" "Bogotá" --out leads.xlsx
```
Esto ejecutará el pipeline completo y guardará el resultado en `leads.xlsx`.

## 4. Uso de la API

El sistema también provee una API REST protegida por `API_KEY` (excepto `/health`).

### Endpoints principales:
- **`POST /api/v1/jobs`**: Inicia un trabajo asíncrono.
  *Body:* `{"keyword": "restaurantes", "location": "Bogotá", "sources": ["demo-directory"], "max_results": 100}`
- **`GET /api/v1/jobs/{id}`**: Revisa el estado del trabajo y la cantidad de leads encontrados.
- **`GET /api/v1/leads`**: Consulta los leads almacenados (soporta filtros por puntaje mínimo, categoría y búsqueda de texto completo).
- **`GET /api/v1/leads/export?format=xlsx`**: Exporta los leads directamente a un archivo (formatos soportados: `xlsx`, `csv`, `json`).

## 5. Cómo agregar una nueva fuente

La arquitectura está diseñada usando adaptadores con una interfaz común. Para agregar una nueva fuente (por ejemplo, un directorio de empresas real):
1. Crea un archivo en `app/sources/` que herede de `SourceAdapter`.
2. Implementa el método `search(keyword, location) -> list[RawLead]`.
3. ¡Listo! El pipeline central (`BackgroundTasks`) se encargará de llamar a la fuente, normalizar los resultados, validarlos, deduplicarlos y puntuarlos sin que debas modificar nada más.

## 6. Límites Legales y Éticos (Nota Importante)

**Nota sobre Google Maps, Proxies y Stealth:**  
En versiones conceptuales o planes previos se consideraba el uso de proxies rotativos, tácticas para ocultar el navegador (stealth) y hacer scraping directo a Google Maps. Hemos decidido **eliminar por completo estas técnicas**.

*¿Por qué?* Evadir bloqueos activos o hacer scraping directo de servicios como Google Maps viola sus Términos de Servicio, lo que representa un riesgo legal y operativo inaceptable tanto para ti como cliente.

**En su lugar, usamos scraping educado y legal:**
- **Sitios y Directorios:** Respetamos estrictamente los archivos `robots.txt`, enviamos un `User-Agent` identificable, aplicamos límites de velocidad (ej. 1 petición por segundo) y gestionamos los bloqueos temporales de forma civilizada (retroceso exponencial ante errores 429).
- **Google Maps:** Solo se consulta de forma opcional mediante la **API Oficial de Google Places** (Text Search), utilizando una llave legítima si el cliente la proporciona.
