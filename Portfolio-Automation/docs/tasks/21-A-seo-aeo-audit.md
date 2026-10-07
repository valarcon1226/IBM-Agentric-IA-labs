# 21-A · Auditoría SEO/AEO automática (informe para clientes)

Carpeta nueva: `Portfolio-Automation/21-seo-aeo-audit` (solo esta). Para gigs de SEO/AEO y de páginas web: se ofrece
una auditoría gratis generada en un minuto como gancho de venta.

1. CLI y API (FastAPI): recibe una URL, rastrea hasta N páginas del mismo dominio (respeta `robots.txt`, límite de
   páginas y de velocidad, User-Agent identificable). Valida la URL (solo http/https, sin IPs privadas salvo
   `--allow-local` para probar con localhost).
2. Revisiones por página: title y meta description (largo, duplicados), un H1, jerarquía de encabezados, canonical,
   `lang`, Open Graph, imágenes sin `alt` o pesadas, links rotos (internos), JSON-LD presente y válido (tipo
   detectado). Del sitio: `sitemap.xml`, `robots.txt`, `llms.txt`, HTTPS, páginas sin enlazar.
3. AEO (respuestas de IA): preguntas como encabezados, respuestas cortas bajo cada pregunta, schema FAQ/HowTo/
   LocalBusiness, datos de contacto y horario legibles como texto. Puntaje 0–100 con criterios explicados.
4. Lighthouse (`npx lighthouse` headless) sobre la página de inicio: los 4 puntajes. Si no hay Chrome, se omite y
   el informe lo dice.
5. Informe HTML (y opción PDF) en español o inglés: resumen ejecutivo (el LLM local lo redacta si está disponible;
   si no, una plantilla), problemas ordenados por impacto con cómo arreglarlos, y lo que está bien.
6. Tests pytest con un sitio de prueba servido localmente (fixtures HTML con errores conocidos) que verifican cada
   regla. Corre una auditoría real contra el sitio del 16 (`http://localhost:8016`, levántalo y apágalo al final)
   y guarda el informe en `samples/`.
7. `README.md` en español para vender el servicio + `docs/DEMO-SCRIPT.md`. `docs/WEBFLOW-GUIA.md`: contenido,
   estructura de páginas y guía paso a paso para que la dueña arme a mano en Webflow (plan gratis) el sitio de
   "Café de Origen" (el lote B lo hace ella, no tú).

Verificación (salida real): `pytest -q`, `ruff check .`, la auditoría contra el 16 (resumen de puntajes), y al final
`docker compose stop` del 16.

Reglas: ponytail, sin commit ni push, sin secretos, no toques otras carpetas.
Al terminar escribe `docs/reviews/T-21-A.md` (español) con la salida real de cada comando.
