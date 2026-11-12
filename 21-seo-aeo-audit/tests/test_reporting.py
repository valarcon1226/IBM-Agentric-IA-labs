"""Tests for report rendering and PDF generation."""

import os
import tempfile

from app.reporting.generator import (
    build_audit_report,
    calculate_seo_score,
    generate_template_executive_summary,
)
from app.reporting.pdf import generate_pdf_from_html


def test_calculate_seo_score():
    """Score decreases appropriately with issue severities."""
    assert calculate_seo_score([]) == 100
    assert calculate_seo_score([{"severity": "CRITICAL"}]) == 85
    assert calculate_seo_score([{"severity": "HIGH"}]) == 90
    assert calculate_seo_score([{"severity": "MEDIUM"}]) == 95
    assert calculate_seo_score([{"severity": "LOW"}]) == 98


def test_generate_template_executive_summary_languages():
    """Generates coherent executive summaries in Spanish and English."""
    issues = [
        {
            "severity": "CRITICAL",
            "category": "SEO On-Page",
            "message": "Falta H1",
            "fix": "Añade H1",
        }
    ]
    summary_es = generate_template_executive_summary(
        "https://ejemplo.com", 75, 80, 70, issues, lang="es"
    )
    assert "https://ejemplo.com" in summary_es
    assert "Prioridad 1" in summary_es

    summary_en = generate_template_executive_summary(
        "https://ejemplo.com", 75, 80, 70, issues, lang="en"
    )
    assert "https://ejemplo.com" in summary_en
    assert "Priority 1" in summary_en


def test_build_audit_report_renders_html():
    """build_audit_report compiles metrics into HTML output."""
    mock_crawler = {
        "pages": [{"url": "https://ejemplo.com/", "response_time_ms": 120}],
    }
    page_analyses = [{
        "url": "https://ejemplo.com/",
        "title": "Ejemplo",
        "h1": ["H1 Ejemplo"],
        "json_ld_types": ["LocalBusiness"],
        "issues": [{"severity": "MEDIUM", "category": "SEO", "message": "Meta corta", "url": "https://ejemplo.com/", "fix": "Alargar"}],
        "good_points": ["Título presente"],
    }]
    site_analysis = {
        "issues": [],
        "good_points": ["robots.txt presente"],
    }
    aeo_analysis = {
        "score": 85,
        "criteria_breakdown": [
            {"criterion": "Preguntas", "points": 25, "max_points": 25, "details": "Bien"}
        ],
        "issues": [],
        "good_points": ["Preguntas detectadas"],
    }
    lighthouse = {
        "available": True,
        "performance": 90,
        "accessibility": 95,
        "best_practices": 100,
        "seo": 92,
    }

    report = build_audit_report(
        target_url="https://ejemplo.com/",
        crawler_result=mock_crawler,
        page_analyses=page_analyses,
        site_analysis=site_analysis,
        aeo_analysis=aeo_analysis,
        lighthouse_result=lighthouse,
        lang="es",
    )

    assert "html_report" in report
    html = report["html_report"]
    assert "SEO &amp; AEO" in html
    assert "https://ejemplo.com/" in html
    assert "Preguntas" in html
    assert "Meta corta" in html


def test_generate_pdf_from_html():
    """PDF generator produces a valid non-empty PDF file."""
    html_content = "<html><body><h1>Reporte de Prueba</h1><p>Contenido para validar PDF.</p></body></html>"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_pdf_path = tmp.name

    try:
        out_pdf = generate_pdf_from_html(html_content, tmp_pdf_path)
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 1000
    finally:
        if os.path.exists(tmp_pdf_path):
            try:
                os.remove(tmp_pdf_path)
            except OSError:
                pass
