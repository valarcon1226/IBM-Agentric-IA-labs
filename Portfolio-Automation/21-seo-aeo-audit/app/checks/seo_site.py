"""Site-level SEO audit checks."""

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse


def parse_sitemap_urls(xml_text: str) -> list[str]:
    """Parse URLs from a standard sitemap.xml or sitemap index."""
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        # Strip namespaces if present
        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text:
                urls.append(elem.text.strip())
    except ET.ParseError:
        pass
    return urls


def analyze_site_seo(
    base_url: str,
    sitemap_response: tuple[int, str] | None = None,
    robots_response: tuple[int, str] | None = None,
    llms_response: tuple[int, str] | None = None,
    https_status: dict[str, Any] | None = None,
    crawled_pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Run site-level checks: sitemap.xml, robots.txt, llms.txt, HTTPS, orphan pages,
    and duplicate titles/meta descriptions.
    """
    issues: list[dict[str, Any]] = []
    good_points: list[str] = []
    crawled_pages = crawled_pages or []

    # 1. Sitemap.xml
    sitemap_found = False
    sitemap_valid = False
    sitemap_urls: list[str] = []

    if sitemap_response:
        status, content = sitemap_response
        if status == 200 and content:
            sitemap_found = True
            sitemap_urls = parse_sitemap_urls(content)
            if sitemap_urls or "<urlset" in content or "<sitemapindex" in content:
                sitemap_valid = True
                good_points.append(
                    f"sitemap.xml encontrado y válido ({len(sitemap_urls)} URLs declaradas)."
                )

    if not sitemap_found:
        issues.append({
            "code": "MISSING_SITEMAP",
            "category": "Indexabilidad del Sitio",
            "severity": "HIGH",
            "message": "No se encontró el archivo sitemap.xml en la raíz del sitio (HTTP 404/Error).",
            "url": f"{base_url.rstrip('/')}/sitemap.xml",
            "fix": "Genera y publica un archivo sitemap.xml en la raíz del dominio para guiar a los motores de búsqueda.",
        })
    elif not sitemap_valid:
        issues.append({
            "code": "INVALID_SITEMAP",
            "category": "Indexabilidad del Sitio",
            "severity": "HIGH",
            "message": "El archivo sitemap.xml no contiene una estructura XML estándar reconocible.",
            "url": f"{base_url.rstrip('/')}/sitemap.xml",
            "fix": "Verifica que el sitemap cumpla con el estándar sitemaps.org (nodos <urlset> y <url><loc>).",
        })

    # 2. Robots.txt
    robots_found = False
    robots_has_sitemap = False
    if robots_response:
        status, content = robots_response
        if status == 200 and content:
            robots_found = True
            lines = content.splitlines()
            for line in lines:
                if line.strip().lower().startswith("sitemap:"):
                    robots_has_sitemap = True
                    break
            good_points.append("Archivo robots.txt presente y accesible.")
            if robots_has_sitemap:
                good_points.append("robots.txt referencia la ubicación del sitemap.")
            else:
                issues.append({
                    "code": "ROBOTS_NO_SITEMAP_DIRECTIVE",
                    "category": "Indexabilidad del Sitio",
                    "severity": "LOW",
                    "message": "El archivo robots.txt no incluye la directiva 'Sitemap:'.",
                    "url": f"{base_url.rstrip('/')}/robots.txt",
                    "fix": "Añade una línea 'Sitemap: https://tu-dominio.com/sitemap.xml' al final de robots.txt.",
                })

    if not robots_found:
        issues.append({
            "code": "MISSING_ROBOTS_TXT",
            "category": "Indexabilidad del Sitio",
            "severity": "MEDIUM",
            "message": "No se detectó un archivo robots.txt en la raíz del sitio.",
            "url": f"{base_url.rstrip('/')}/robots.txt",
            "fix": "Crea un archivo robots.txt configurando permisos de rastreo para User-Agents y enlazando tu sitemap.",
        })

    # 3. llms.txt (estándar emergente para crawlers de IA / LLMs)
    llms_found = False
    if llms_response:
        status, content = llms_response
        if status == 200 and content and len(content.strip()) > 10:
            llms_found = True
            good_points.append("Archivo llms.txt detectado: el sitio está preparado para indexación por IA.")

    if not llms_found:
        issues.append({
            "code": "MISSING_LLMS_TXT",
            "category": "Preparación para IA (AEO)",
            "severity": "LOW",
            "message": "No se encontró el archivo llms.txt ni /.well-known/llms.txt.",
            "url": f"{base_url.rstrip('/')}/llms.txt",
            "fix": "Crea un archivo llms.txt en markdown con un resumen conciso del negocio y enlaces clave para crawlers de IA (Perplexity, ChatGPT Search, Gemini).",
        })

    # 4. HTTPS
    https_status = https_status or {}
    is_https = https_status.get("is_https", base_url.startswith("https://"))
    is_local = https_status.get("is_local", False)

    if not is_https and not is_local:
        issues.append({
            "code": "NOT_USING_HTTPS",
            "category": "Seguridad y Confianza",
            "severity": "CRITICAL",
            "message": "El sitio se sirve a través de HTTP sin cifrado TLS/SSL.",
            "url": base_url,
            "fix": "Instala un certificado SSL gratuito con Let's Encrypt y fuerza redirección 301 de HTTP a HTTPS.",
        })
    elif is_https:
        good_points.append("Conexión segura mediante HTTPS activa.")

    # 5. Duplicados entre páginas rastreadas (Title & Meta description)
    title_to_urls: dict[str, list[str]] = {}
    desc_to_urls: dict[str, list[str]] = {}

    for page in crawled_pages:
        p_url = page.get("url", "")
        t = page.get("title", "").strip()
        d = page.get("meta_description", "").strip()

        if t:
            title_to_urls.setdefault(t, []).append(p_url)
        if d:
            desc_to_urls.setdefault(d, []).append(p_url)

    duplicate_titles = {t: urls for t, urls in title_to_urls.items() if len(urls) > 1}
    duplicate_descs = {d: urls for d, urls in desc_to_urls.items() if len(urls) > 1}

    if duplicate_titles:
        issues.append({
            "code": "DUPLICATE_TITLES",
            "category": "SEO On-Page",
            "severity": "HIGH",
            "message": f"Se detectaron {len(duplicate_titles)} títulos duplicados entre diferentes páginas rastreadas.",
            "url": base_url,
            "fix": "Personaliza el <title> de cada página para que sea 100% único y refleje su contenido exclusivo.",
            "details": duplicate_titles,
        })
    elif len(crawled_pages) > 1:
        good_points.append("Títulos únicos en todas las páginas rastreadas.")

    if duplicate_descs:
        issues.append({
            "code": "DUPLICATE_META_DESCRIPTIONS",
            "category": "SEO On-Page",
            "severity": "MEDIUM",
            "message": f"Se detectaron {len(duplicate_descs)} meta descripciones duplicadas entre páginas rastreadas.",
            "url": base_url,
            "fix": "Redacta una meta descripción original y específica para cada página.",
            "details": duplicate_descs,
        })

    # 6. Páginas huérfanas (Orphan pages): URLs en sitemap.xml no enlazadas internamente
    crawled_urls = {p.get("url", "").rstrip("/") for p in crawled_pages}
    # normalize paths
    crawled_paths = {urlparse(u).path.rstrip("/") for u in crawled_urls if u}

    orphan_pages: list[str] = []
    for sm_url in sitemap_urls:
        sm_clean = sm_url.rstrip("/")
        sm_path = urlparse(sm_clean).path.rstrip("/")
        if sm_clean not in crawled_urls and sm_path not in crawled_paths:
            orphan_pages.append(sm_url)

    if orphan_pages:
        issues.append({
            "code": "ORPHAN_PAGES_IN_SITEMAP",
            "category": "Estructura de Enlaces",
            "severity": "MEDIUM",
            "message": f"Se identificaron {len(orphan_pages)} páginas en el sitemap.xml sin enlaces internos directos descubiertos.",
            "url": base_url,
            "fix": "Enlaza estas páginas desde el menú principal, footer o contenido contextual para que reciban flujo de autoridad.",
            "details": orphan_pages[:10],
        })
    elif sitemap_valid and len(sitemap_urls) > 0:
        good_points.append("Todas las páginas analizadas cuentan con enlaces internos coherentes.")

    return {
        "sitemap_found": sitemap_found,
        "sitemap_valid": sitemap_valid,
        "sitemap_urls_count": len(sitemap_urls),
        "robots_found": robots_found,
        "robots_has_sitemap": robots_has_sitemap,
        "llms_found": llms_found,
        "is_https": is_https,
        "duplicate_titles_count": len(duplicate_titles),
        "duplicate_descs_count": len(duplicate_descs),
        "orphan_pages": orphan_pages,
        "issues": issues,
        "good_points": good_points,
    }
