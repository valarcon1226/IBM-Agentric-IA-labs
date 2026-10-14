# Auditoría SEO & AEO Automática para Clientes

Herramienta profesional de diagnóstico y prospección comercial en Python (CLI + FastAPI). Genera en **menos de 60 segundos** un informe exhaustivo de **SEO Técnico, On-Page, Core Web Vitals (Lighthouse) y AEO (Answer Engine Optimization para ChatGPT, Perplexity y Gemini)**, diseñado como gancho de venta irresistible para cerrar gigs de páginas web y posicionamiento digital.

---

## Por qué existe este proyecto (Gancho Comercial)

El 90% de los dueños de negocios locales y pymes no compran servicios de desarrollo web ni consultoría SEO porque no entienden los términos técnicos abstractos. Sin embargo, cuando ven un **informe personalizado con la URL de su propio negocio**, con calificaciones claras (0 a 100), problemas ordenados por impacto financiero y la explicación exacta de **por qué los motores de IA no están recomendando su marca**, la venta se cierra sola.

Este software permite:
1. **Atraer prospectos fríos**: Ofrecer una *"Auditoría Digital de 60 segundos gratis"* en LinkedIn, WhatsApp o correo en frío.
2. **Evidenciar fallas en tiempo real**: Presentar problemas críticos con instrucciones exactas de cómo corregirlos.
3. **Puntaje AEO Pionero**: Evaluar la preparación del sitio para el nuevo paradigma de búsqueda (respuestas directas en ChatGPT Search, Perplexity, Google AI Overviews).
4. **Vender el servicio de corrección o rediseño web**: Posicionar tus servicios (ej. migración a Webflow, WordPress optimizado o modernización de frontend) como la solución inmediata.

---

## Qué revisa la auditoría

### 1. Revisiones SEO por Página (On-Page)
- **Título (`<title>`)**: Presencia, longitud óptima (30–60 caracteres) y detección de títulos duplicados.
- **Meta Descripción**: Presencia, longitud (70–160 caracteres) y contenido persuasivo.
- **Etiqueta `<h1>`**: Exactamente un H1 por página (alerta ante ausencia o múltiples H1s).
- **Jerarquía de Encabezados**: Validación secuencial (evita saltos arbitrarios de H1 a H3 o H4).
- **Enlace Canónico (`rel="canonical"`)**: Verificación de URL absoluta para evitar contenido duplicado.
- **Idioma (`<html lang="...">`)**: Declaración correcta para buscadores y accesibilidad.
- **Open Graph**: Presencia de `og:title`, `og:description`, `og:image` y `og:url` para previsualizaciones impecables en WhatsApp y redes sociales.
- **Imágenes**: Detección de imágenes sin atributo `alt` e identificación de imágenes pesadas (> 200 KB).
- **Enlaces Internos**: Extracción de enlaces del mismo dominio y detección automática de enlaces rotos (error 404 / 500).
- **Datos Estructurados (JSON-LD)**: Sintaxis JSON válida y tipos schema detectados (`LocalBusiness`, `Restaurant`, `FAQPage`, `HowTo`, etc.).

### 2. Revisiones del Sitio Completo (Técnico)
- **`sitemap.xml`**: Existencia en raíz, estructura XML válida y conteo de URLs declaradas.
- **`robots.txt`**: Existencia, directivas de rastreo y enlace al sitemap.
- **`llms.txt`**: Comprobación del estándar emergente para indexación por modelos de lenguaje e IA.
- **HTTPS**: Certificado seguro activo y forzado de redirección.
- **Páginas Huérfanas**: Identificación de URLs presentes en el `sitemap.xml` que no están enlazadas internamente.

### 3. AEO (Answer Engine Optimization) — Puntaje 0 a 100
Evaluación específica de qué tan fácil es para un asistente de IA extraer respuestas sobre el negocio:
1. **Preguntas como encabezados (25 pts)**: Encabezados formulados como preguntas directas de clientes.
2. **Respuestas concisas bajo cada pregunta (25 pts)**: Párrafos de respuesta directa inmediatos (< 300 caracteres).
3. **Schema FAQ / HowTo / LocalBusiness (25 pts)**: Datos estructurados especializados para evitar alucinaciones en modelos de IA.
4. **Contacto y Horarios legibles como texto plano (25 pts)**: Teléfono, email, dirección y horarios accesibles en el HTML body (no ocultos dentro de imágenes).

### 4. Core Web Vitals (Lighthouse Headless)
- Ejecución desatendida de `npx lighthouse` sobre la página principal.
- Extracción de los 4 puntajes oficiales: **Rendimiento, Accesibilidad, Mejores Prácticas y SEO**.
- Si no hay navegador disponible, el informe lo indica limpiamente sin fallar.

### 5. Informes para Clientes (HTML y PDF)
- **HTML interactivo**: Diseño responsivo de alta gama con tarjetas visuales, desglose AEO, listado de fortalezas y tabla de problemas con recomendaciones paso a paso.
- **Resumen Ejecutivo**: Redactado automáticamente por LLM local (Ollama) si está activo, o mediante plantilla dinámica de consultoría senior orientada a conversión.
- **Exportación PDF**: Generación directa en PDF mediante el motor nativo de Microsoft Edge / Chromium.

---

## Instalación y Requisitos

### Requisitos
- Python 3.12+ (o `uv`)
- Node.js y npm (para Lighthouse y Playwright)
- Microsoft Edge o Google Chrome (instalado en el sistema)

### Configuración rápida con `uv`:
```powershell
cd 21-seo-aeo-audit
uv venv .venv
uv pip install -p .venv\Scripts\python.exe -r requirements-dev.txt
```

---

## Guía de Uso

### 1. Vía Línea de Comandos (CLI)

Auditar un sitio web público:
```powershell
.venv\Scripts\python.exe -m app.cli https://ejemplo.com --max-pages 10 --output samples/informe.html --pdf samples/informe.pdf
```

Auditar un sitio local de desarrollo (omitiendo protección SSRF):
```powershell
.venv\Scripts\python.exe -m app.cli http://localhost:8016 --allow-local --max-pages 5 --output samples/informe-local.html
```

Opciones disponibles en el CLI:
- `url`: URL obligatoria a auditar (`http://` o `https://`).
- `--max-pages`: Límite de páginas del mismo dominio a rastrear (defecto: `10`).
- `--allow-local`: Habilita la auditoría en `localhost` y direcciones IP privadas.
- `--skip-lighthouse`: Omite la ejecución de Lighthouse para auditorías ultra rápidas (1-2 segundos).
- `--lang`: Idioma del informe (`es` o `en`, defecto: `es`).
- `-o, --output`: Ruta donde guardar el informe HTML.
- `--pdf`: Ruta donde guardar el informe exportado en PDF.

---

### 2. Vía API REST (FastAPI)

Iniciar el servidor API:
```powershell
.venv\Scripts\python.exe -m uvicorn app.api:app --host 0.0.0.0 --port 8021 --reload
```

Documentación interactiva disponible en: `http://localhost:8021/docs`

#### Endpoints principales:
- `GET /health`: Estado del servicio.
- `POST /audit`: Retorna el modelo de auditoría en JSON estructurado.
- `POST /audit/html`: Retorna el informe HTML renderizado listo para ver en el navegador.
- `POST /audit/pdf`: Genera y descarga el informe en formato PDF.

Ejemplo de petición con `curl`:
```bash
curl -X POST http://localhost:8021/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ejemplo.com", "max_pages": 5, "lang": "es"}'
```

---

## Pruebas Automatizadas

La suite incluye 28 pruebas unitarias y de integración que verifican cada regla sobre fixtures controlados y un servidor HTTP de pruebas:
```powershell
.venv\Scripts\pytest.exe -q
```

Verificación de estándares de código y tipado con Ruff:
```powershell
.venv\Scripts\ruff.exe check .
```

---

## Estructura del Proyecto

```
21-seo-aeo-audit/
├── app/
│   ├── config.py             # Constantes y umbrales (pesos, caracteres, timeouts)
│   ├── validators.py         # Validación estricta de URL y prevención SSRF
│   ├── crawler.py            # Rastreador asíncrono con respeto a robots.txt
│   ├── checks/
│   │   ├── seo_page.py       # Título, meta, H1, jerarquía, canonical, OG, imágenes, links, JSON-LD
│   │   ├── seo_site.py       # Sitemap.xml, robots.txt, llms.txt, HTTPS, páginas huérfanas
│   │   └── aeo.py            # Preguntas, respuestas concisas, schema y contacto en texto (0-100)
│   ├── lighthouse.py         # Ejecución desatendida de Lighthouse con fallback elegante
│   ├── reporting/
│   │   ├── generator.py      # Modelo unificado, resumen ejecutivo dinámico / LLM y traducciones
│   │   ├── pdf.py            # Generación de PDF headless vía Edge
│   │   └── templates/
│   │       └── report.html   # Plantilla HTML responsiva para clientes
│   ├── api.py                # Endpoints FastAPI
│   └── cli.py                # Interfaz de consola
├── docs/
│   ├── DEMO-SCRIPT.md        # Guion comercial de 5 minutos para llamadas de venta
│   └── WEBFLOW-GUIA.md       # Guía paso a paso para armar el sitio de Café de Origen en Webflow
├── samples/                  # Informes de muestra generados
├── tests/                    # 28 pruebas pytest con fixtures HTML y servidor local
├── pyproject.toml            # Configuración ruff y pytest
├── requirements.txt          # Dependencias de producción
└── requirements-dev.txt      # Dependencias de desarrollo
```
