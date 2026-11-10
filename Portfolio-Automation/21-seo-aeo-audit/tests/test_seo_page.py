"""Tests for page-level SEO checks."""

from app.checks.seo_page import analyze_page_seo, extract_internal_links


def test_perfect_page_seo(perfect_html: str):
    """A well-configured page passes all SEO checks with no critical issues."""
    res = analyze_page_seo(
        url="https://ejemplo.com/cafe-origen",
        html=perfect_html,
        status_code=200,
    )

    assert res["title"] == "Café Especial de Origen | Tostión Artesanal"
    assert 30 <= res["title_length"] <= 60
    assert 70 <= res["meta_description_length"] <= 160
    assert res["h1_count"] == 1
    assert res["canonical"] == "https://ejemplo.com/cafe-origen"
    assert res["lang"] == "es"
    assert res["has_og"] is True
    assert res["images_missing_alt"] == []
    assert res["json_ld_valid"] is True
    assert "LocalBusiness" in res["json_ld_types"]
    assert "FAQPage" in res["json_ld_types"]

    # No critical or high issues
    critical_or_high = [
        i for i in res["issues"] if i["severity"] in ("CRITICAL", "HIGH")
    ]
    assert len(critical_or_high) == 0


def test_broken_page_seo(broken_seo_html: str):
    """Broken page triggers all targeted SEO issue codes."""
    res = analyze_page_seo(
        url="https://ejemplo.com/broken",
        html=broken_seo_html,
        status_code=200,
        broken_links=["https://ejemplo.com/enlace-roto-404"],
        image_sizes={"/images/banner.png": 300 * 1024},  # 300 KB -> heavy
    )

    issue_codes = {i["code"] for i in res["issues"]}

    assert "MISSING_TITLE" in issue_codes
    assert "MISSING_META_DESCRIPTION" in issue_codes
    assert "MULTIPLE_H1" in issue_codes
    assert "INVALID_HEADING_HIERARCHY" in issue_codes
    assert "MISSING_CANONICAL" in issue_codes
    assert "MISSING_HTML_LANG" in issue_codes
    assert "INCOMPLETE_OPEN_GRAPH" in issue_codes
    assert "IMAGES_MISSING_ALT" in issue_codes
    assert "HEAVY_IMAGES" in issue_codes
    assert "BROKEN_INTERNAL_LINKS" in issue_codes
    assert "INVALID_JSON_LD" in issue_codes


def test_extract_internal_links():
    """Extracts same-origin links and filters external or anchor links."""
    html = """
    <html>
      <body>
        <a href="/about">About</a>
        <a href="https://ejemplo.com/menu">Menu</a>
        <a href="https://google.com/external">External</a>
        <a href="#section">Anchor</a>
        <a href="mailto:info@ejemplo.com">Mailto</a>
      </body>
    </html>
    """
    links = extract_internal_links("https://ejemplo.com/home", html)
    assert "https://ejemplo.com/about" in links
    assert "https://ejemplo.com/menu" in links
    assert not any("google.com" in link for link in links)
    assert not any("#" in link for link in links)
