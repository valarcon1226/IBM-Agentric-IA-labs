"""Page-level SEO audit checks."""

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import DEFAULT_CONFIG


def analyze_page_seo(
    url: str,
    html: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    image_sizes: dict[str, int] | None = None,
    broken_links: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run all per-page SEO checks on the provided HTML document.
    """
    soup = BeautifulSoup(html, "html.parser")
    headers = headers or {}
    image_sizes = image_sizes or {}
    broken_links = broken_links or []

    issues: list[dict[str, Any]] = []
    good_points: list[str] = []

    # 1. Title
    title_tag = soup.find("title")
    title_text = title_tag.get_text().strip() if title_tag else ""
    title_len = len(title_text)

    if not title_text:
        issues.append({
            "code": "MISSING_TITLE",
            "category": "SEO On-Page",
            "severity": "CRITICAL",
            "message": "La página no tiene etiqueta <title> o está vacía.",
            "url": url,
            "fix": "Agrega una etiqueta <title> descriptiva de entre 30 y 60 caracteres que incluya la palabra clave principal.",
        })
    elif title_len < DEFAULT_CONFIG.title_min_length:
        issues.append({
            "code": "TITLE_TOO_SHORT",
            "category": "SEO On-Page",
            "severity": "MEDIUM",
            "message": f"El título es demasiado corto ({title_len} caracteres): '{title_text}'.",
            "url": url,
            "fix": f"Amplía el título para alcanzar entre {DEFAULT_CONFIG.title_min_length} y {DEFAULT_CONFIG.title_max_length} caracteres, agregando contexto de marca o servicio.",
        })
    elif title_len > DEFAULT_CONFIG.title_max_length:
        issues.append({
            "code": "TITLE_TOO_LONG",
            "category": "SEO On-Page",
            "severity": "MEDIUM",
            "message": f"El título es demasiado largo ({title_len} caracteres): '{title_text}'. Los buscadores lo recortarán.",
            "url": url,
            "fix": f"Reduce el título a menos de {DEFAULT_CONFIG.title_max_length} caracteres para evitar truncamiento en las SERP de Google.",
        })
    else:
        good_points.append(f"Título optimizado ({title_len} caracteres): '{title_text}'.")

    # 2. Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc_text = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    meta_desc_len = len(meta_desc_text)

    if not meta_desc_text:
        issues.append({
            "code": "MISSING_META_DESCRIPTION",
            "category": "SEO On-Page",
            "severity": "MEDIUM",
            "message": "Falta la meta descripción (<meta name='description'>).",
            "url": url,
            "fix": "Añade una meta descripción persuasiva de entre 70 y 160 caracteres con llamada a la acción.",
        })
    elif meta_desc_len < DEFAULT_CONFIG.description_min_length:
        issues.append({
            "code": "META_DESCRIPTION_TOO_SHORT",
            "category": "SEO On-Page",
            "severity": "LOW",
            "message": f"La meta descripción es corta ({meta_desc_len} caracteres).",
            "url": url,
            "fix": f"Extiende la meta descripción a un mínimo de {DEFAULT_CONFIG.description_min_length} caracteres para mejorar el CTR orgánico.",
        })
    elif meta_desc_len > DEFAULT_CONFIG.description_max_length:
        issues.append({
            "code": "META_DESCRIPTION_TOO_LONG",
            "category": "SEO On-Page",
            "severity": "LOW",
            "message": f"La meta descripción excede el límite recomendado ({meta_desc_len} caracteres).",
            "url": url,
            "fix": f"Ajusta la meta descripción a un máximo de {DEFAULT_CONFIG.description_max_length} caracteres.",
        })
    else:
        good_points.append(f"Meta descripción bien configurada ({meta_desc_len} caracteres).")

    # 3. H1 count
    h1_tags = soup.find_all("h1")
    h1_texts = [h.get_text().strip() for h in h1_tags if h.get_text().strip()]

    if len(h1_tags) == 0:
        issues.append({
            "code": "MISSING_H1",
            "category": "SEO On-Page",
            "severity": "CRITICAL",
            "message": "La página no contiene ninguna etiqueta <h1>.",
            "url": url,
            "fix": "Define un único encabezado <h1> claro que sintetice la temática central de la página.",
        })
    elif len(h1_tags) > 1:
        issues.append({
            "code": "MULTIPLE_H1",
            "category": "SEO On-Page",
            "severity": "HIGH",
            "message": f"Se encontraron {len(h1_tags)} etiquetas <h1>. Debe existir exactamente una por página.",
            "url": url,
            "fix": "Conserva únicamente un <h1> principal y convierte los demás en <h2> o <h3>.",
        })
    else:
        good_points.append(f"Estructura <h1> única y definida: '{h1_texts[0]}'.")

    # 4. Heading hierarchy
    headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
    hierarchy_errors = []
    last_level = 0
    for h in headings:
        level = int(h.name[1])
        if last_level != 0 and level > last_level + 1:
            hierarchy_errors.append(f"Salto de <h{last_level}> a <h{level}> sin nivel intermedio.")
        last_level = level

    if hierarchy_errors:
        issues.append({
            "code": "INVALID_HEADING_HIERARCHY",
            "category": "Estructura de Contenido",
            "severity": "MEDIUM",
            "message": f"Discontinuidad en la jerarquía de encabezados: {'; '.join(hierarchy_errors)}",
            "url": url,
            "fix": "Organiza los encabezados de forma secuencial (h1 -> h2 -> h3) sin saltar niveles para facilitar la lectura a buscadores y lectores de pantalla.",
        })
    elif len(headings) > 1:
        good_points.append(f"Jerarquía de encabezados coherente ({len(headings)} niveles evaluados).")

    # 5. Canonical
    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
    canonical_href = canonical_tag.get("href", "").strip() if canonical_tag else ""

    if not canonical_href:
        issues.append({
            "code": "MISSING_CANONICAL",
            "category": "Indexación",
            "severity": "MEDIUM",
            "message": "Falta la etiqueta de enlace canonical (<link rel='canonical'>).",
            "url": url,
            "fix": "Añade <link rel='canonical' href='URL_ABSOLUTA'> en el <head> para evitar contenido duplicado.",
        })
    else:
        good_points.append(f"Etiqueta canonical presente: '{canonical_href}'.")

    # 6. HTML Lang
    html_tag = soup.find("html")
    lang_val = html_tag.get("lang", "").strip() if html_tag else ""

    if not lang_val:
        issues.append({
            "code": "MISSING_HTML_LANG",
            "category": "Accesibilidad y SEO",
            "severity": "HIGH",
            "message": "El elemento <html> carece del atributo 'lang' o está vacío.",
            "url": url,
            "fix": "Especifica el idioma del contenido agregando lang='es' (o el código ISO correspondiente) en la etiqueta <html>.",
        })
    else:
        good_points.append(f"Idioma del documento declarado: lang='{lang_val}'.")

    # 7. Open Graph tags
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    og_image = soup.find("meta", attrs={"property": "og:image"})
    og_url = soup.find("meta", attrs={"property": "og:url"})

    missing_og = []
    if not (og_title and og_title.get("content")):
        missing_og.append("og:title")
    if not (og_desc and og_desc.get("content")):
        missing_og.append("og:description")
    if not (og_image and og_image.get("content")):
        missing_og.append("og:image")
    if not (og_url and og_url.get("content")):
        missing_og.append("og:url")

    if missing_og:
        issues.append({
            "code": "INCOMPLETE_OPEN_GRAPH",
            "category": "Redes Sociales y Compartición",
            "severity": "LOW",
            "message": f"Faltan etiquetas Open Graph clave: {', '.join(missing_og)}.",
            "url": url,
            "fix": "Implementa los metadatos Open Graph completos para asegurar previsualizaciones atractivas al compartir en WhatsApp, LinkedIn y redes sociales.",
        })
    else:
        good_points.append("Etiquetas Open Graph esenciales presentes (título, descripción, imagen y URL).")

    # 8. Images without alt or heavy
    img_tags = soup.find_all("img")
    missing_alt_imgs = []
    heavy_imgs = []

    for img in img_tags:
        src = img.get("src") or img.get("data-src") or ""
        alt = img.get("alt")
        # Check alt
        if alt is None or alt.strip() == "":
            missing_alt_imgs.append(src or "imagen_sin_src")

        # Check heavy image
        abs_img_url = urljoin(url, src) if src else ""
        size = image_sizes.get(abs_img_url) or image_sizes.get(src, 0)
        if size > DEFAULT_CONFIG.heavy_image_bytes_threshold:
            size_kb = round(size / 1024, 1)
            heavy_imgs.append(f"{src} ({size_kb} KB)")

    if missing_alt_imgs:
        issues.append({
            "code": "IMAGES_MISSING_ALT",
            "category": "Accesibilidad y SEO",
            "severity": "MEDIUM",
            "message": f"Se encontraron {len(missing_alt_imgs)} imágenes sin texto alternativo (alt).",
            "url": url,
            "fix": "Agrega atributos alt descriptivos y concisos a todas las imágenes informativas.",
            "details": missing_alt_imgs[:5],
        })
    elif len(img_tags) > 0:
        good_points.append(f"Todas las imágenes ({len(img_tags)}) tienen atributo alt definido.")

    if heavy_imgs:
        issues.append({
            "code": "HEAVY_IMAGES",
            "category": "Rendimiento Web",
            "severity": "MEDIUM",
            "message": f"Se detectaron {len(heavy_imgs)} imágenes pesadas (> {DEFAULT_CONFIG.heavy_image_bytes_threshold // 1024} KB).",
            "url": url,
            "fix": "Optimiza y comprime las imágenes a formato WebP o AVIF y dimensiona apropiadamente.",
            "details": heavy_imgs[:5],
        })

    # 9. Broken internal links
    if broken_links:
        issues.append({
            "code": "BROKEN_INTERNAL_LINKS",
            "category": "Enlaces e Indexabilidad",
            "severity": "HIGH",
            "message": f"Se identificaron {len(broken_links)} enlaces internos rotos.",
            "url": url,
            "fix": "Actualiza o redirige los enlaces caídos para no desperdiciar presupuesto de rastreo y evitar frustración al usuario.",
            "details": broken_links[:10],
        })
    else:
        good_points.append("No se detectaron enlaces internos rotos en la página.")

    # 10. JSON-LD structured data
    json_ld_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    detected_types: list[str] = []
    json_ld_valid = True

    for tag in json_ld_tags:
        content = tag.string or tag.get_text()
        if not content:
            continue
        try:
            data = json.loads(content)
            # could be list or dict
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    t = item.get("@type")
                    if isinstance(t, list):
                        detected_types.extend(t)
                    elif t:
                        detected_types.append(str(t))
                    # check for @graph
                    graph = item.get("@graph")
                    if isinstance(graph, list):
                        for g in graph:
                            if isinstance(g, dict) and g.get("@type"):
                                gt = g.get("@type")
                                if isinstance(gt, list):
                                    detected_types.extend(gt)
                                else:
                                    detected_types.append(str(gt))
        except (json.JSONDecodeError, UnicodeDecodeError):
            json_ld_valid = False

    if not json_ld_tags:
        issues.append({
            "code": "MISSING_JSON_LD",
            "category": "Datos Estructurados",
            "severity": "MEDIUM",
            "message": "No se detectó ningún bloque de datos estructurados JSON-LD (<script type='application/ld+json'>).",
            "url": url,
            "fix": "Añade marcado schema.org en formato JSON-LD (ej. LocalBusiness, Organization, WebSite) para enriquecer la presencia en buscadores.",
        })
    elif not json_ld_valid:
        issues.append({
            "code": "INVALID_JSON_LD",
            "category": "Datos Estructurados",
            "severity": "HIGH",
            "message": "Se detectó código JSON-LD con sintaxis inválida o errores de formato JSON.",
            "url": url,
            "fix": "Valida el script JSON-LD con la herramienta de resultados enriquecidos de Google y corrige errores de comas o comillas.",
        })
    else:
        types_str = ", ".join(set(detected_types)) if detected_types else "Genérico"
        good_points.append(f"Datos estructurados JSON-LD válidos presentes (tipo: {types_str}).")

    return {
        "url": url,
        "title": title_text,
        "title_length": title_len,
        "meta_description": meta_desc_text,
        "meta_description_length": meta_desc_len,
        "h1": h1_texts,
        "h1_count": len(h1_tags),
        "heading_count": len(headings),
        "canonical": canonical_href,
        "lang": lang_val,
        "has_og": len(missing_og) == 0,
        "open_graph_missing": missing_og,
        "images_count": len(img_tags),
        "images_missing_alt": missing_alt_imgs,
        "heavy_images": heavy_imgs,
        "json_ld_detected": bool(json_ld_tags),
        "json_ld_valid": json_ld_valid,
        "json_ld_types": sorted(list(set(detected_types))),
        "issues": issues,
        "good_points": good_points,
    }


def extract_internal_links(base_url: str, html: str) -> list[str]:
    """Extract all internal links belonging to the same host/origin."""
    soup = BeautifulSoup(html, "html.parser")
    base_parsed = urlparse(base_url)
    base_host = (base_parsed.netloc or "").lower()

    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:", "whatsapp:")):
            continue
        full_url = urljoin(base_url, raw_href)
        parsed = urlparse(full_url)
        if parsed.scheme in ("http", "https") and (parsed.netloc or "").lower() == base_host:
            # Normalize url by stripping fragment
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            links.add(clean_url)

    return sorted(list(links))
