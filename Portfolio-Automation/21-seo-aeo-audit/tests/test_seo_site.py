"""Tests for site-level SEO checks."""

from app.checks.seo_site import analyze_site_seo, parse_sitemap_urls


def test_parse_sitemap_urls():
    """Correctly parses loc URLs from standard sitemap XML."""
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://ejemplo.com/</loc></url>
      <url><loc>https://ejemplo.com/servicios</loc></url>
    </urlset>
    """
    urls = parse_sitemap_urls(xml_data)
    assert urls == ["https://ejemplo.com/", "https://ejemplo.com/servicios"]


def test_site_seo_perfect_setup():
    """Site with sitemap, robots, llms.txt and https passes checks."""
    sitemap_xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://ejemplo.com/</loc></url>
      <url><loc>https://ejemplo.com/contacto</loc></url>
    </urlset>"""
    robots_txt = "User-agent: *\nAllow: /\nSitemap: https://ejemplo.com/sitemap.xml"
    llms_txt = "# Resumen del negocio para LLMs\nContenido claro."

    crawled_pages = [
        {"url": "https://ejemplo.com/", "title": "Inicio", "meta_description": "Desc 1"},
        {"url": "https://ejemplo.com/contacto", "title": "Contacto", "meta_description": "Desc 2"},
    ]

    res = analyze_site_seo(
        base_url="https://ejemplo.com",
        sitemap_response=(200, sitemap_xml),
        robots_response=(200, robots_txt),
        llms_response=(200, llms_txt),
        https_status={"is_https": True, "is_local": False},
        crawled_pages=crawled_pages,
    )

    assert res["sitemap_found"] is True
    assert res["sitemap_valid"] is True
    assert res["robots_found"] is True
    assert res["robots_has_sitemap"] is True
    assert res["llms_found"] is True
    assert res["is_https"] is True
    assert res["duplicate_titles_count"] == 0
    assert res["orphan_pages"] == []


def test_site_seo_detects_flaws_and_orphan_pages():
    """Detects missing sitemap, robots without sitemap, non-https, duplicate titles, and orphan pages."""
    sitemap_xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>http://mi-sitio.com/</loc></url>
      <url><loc>http://mi-sitio.com/huerfana-1</loc></url>
      <url><loc>http://mi-sitio.com/huerfana-2</loc></url>
    </urlset>"""

    robots_txt = "User-agent: *\nDisallow: /admin/"  # Missing sitemap directive

    crawled_pages = [
        {"url": "http://mi-sitio.com/", "title": "Mismo Título", "meta_description": "Misma desc"},
        {"url": "http://mi-sitio.com/otra", "title": "Mismo Título", "meta_description": "Misma desc"},
    ]

    res = analyze_site_seo(
        base_url="http://mi-sitio.com",
        sitemap_response=(200, sitemap_xml),
        robots_response=(200, robots_txt),
        llms_response=(404, ""),
        https_status={"is_https": False, "is_local": False},
        crawled_pages=crawled_pages,
    )

    issue_codes = {i["code"] for i in res["issues"]}

    assert "NOT_USING_HTTPS" in issue_codes
    assert "MISSING_LLMS_TXT" in issue_codes
    assert "ROBOTS_NO_SITEMAP_DIRECTIVE" in issue_codes
    assert "DUPLICATE_TITLES" in issue_codes
    assert "DUPLICATE_META_DESCRIPTIONS" in issue_codes
    assert "ORPHAN_PAGES_IN_SITEMAP" in issue_codes
    assert len(res["orphan_pages"]) == 2
