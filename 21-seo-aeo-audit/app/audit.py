"""High-level audit orchestrator."""

import asyncio
from typing import Any

from app.checks.aeo import analyze_aeo
from app.checks.seo_page import analyze_page_seo
from app.checks.seo_site import analyze_site_seo
from app.crawler import SiteCrawler
from app.lighthouse import run_lighthouse_audit
from app.reporting.generator import build_audit_report
from app.reporting.pdf import generate_pdf_from_html
from app.validators import validate_url


async def run_full_audit(
    url: str,
    max_pages: int = 10,
    allow_local: bool = False,
    run_lighthouse: bool = True,
    lang: str = "es",
    pdf_output_path: str | None = None,
) -> dict[str, Any]:
    """
    Execute full automated SEO and AEO audit:
    - URL & IP security validation
    - Polite crawler with robots.txt adherence
    - Page-level SEO checks (title, meta, h1, hierarchy, canonical, lang, OG, images, links, JSON-LD)
    - Site-level SEO checks (sitemap, robots, llms.txt, https, orphan pages, duplicates)
    - AEO (AI Answers) 0-100 scoring
    - Lighthouse 4-score extraction
    - Report generation (HTML & optional PDF)
    """
    # 1. URL Validation
    validated_url = validate_url(url, allow_local=allow_local)

    # 2. Crawl domain
    crawler = SiteCrawler(allow_local=allow_local)
    crawl_data = await crawler.crawl(validated_url, max_pages=max_pages)

    pages = crawl_data.get("pages", [])
    if not pages:
        raise RuntimeError(f"No fue posible rastrear páginas desde {validated_url}.")

    # 3. Analyze each page
    page_analyses = []
    root_json_ld_types = []
    for idx, page in enumerate(pages):
        p_analysis = analyze_page_seo(
            url=page["url"],
            html=page["html"],
            status_code=page["status_code"],
            headers=page["headers"],
            image_sizes=page.get("image_sizes", {}),
            broken_links=page.get("broken_links", []),
        )
        page_analyses.append(p_analysis)
        if idx == 0:
            root_json_ld_types = p_analysis.get("json_ld_types", [])

    # 4. Site-level analysis
    site_analysis = analyze_site_seo(
        base_url=validated_url,
        sitemap_response=crawl_data.get("sitemap_response"),
        robots_response=crawl_data.get("robots_response"),
        llms_response=crawl_data.get("llms_response"),
        https_status={
            "is_https": crawl_data.get("is_https", False),
            "is_local": crawl_data.get("is_local", False),
        },
        crawled_pages=page_analyses,
    )

    # 5. AEO Analysis (on root page)
    root_html = pages[0]["html"]
    aeo_analysis = analyze_aeo(
        url=pages[0]["url"],
        html=root_html,
        json_ld_types=root_json_ld_types,
    )

    # 6. Lighthouse on root page
    if run_lighthouse:
        # Run lighthouse in thread pool to avoid blocking the asyncio loop
        loop = asyncio.get_running_loop()
        lighthouse_res = await loop.run_in_executor(None, run_lighthouse_audit, validated_url)
    else:
        lighthouse_res = {
            "available": False,
            "skipped": True,
            "reason": "Lighthouse omitido por configuración.",
            "performance": None,
            "accessibility": None,
            "best_practices": None,
            "seo": None,
        }

    # 7. Generate unified report
    report = build_audit_report(
        target_url=validated_url,
        crawler_result=crawl_data,
        page_analyses=page_analyses,
        site_analysis=site_analysis,
        aeo_analysis=aeo_analysis,
        lighthouse_result=lighthouse_res,
        lang=lang,
    )

    # 8. Optional PDF export
    if pdf_output_path:
        generate_pdf_from_html(report["html_report"], pdf_output_path)
        report["pdf_path"] = pdf_output_path

    return report
