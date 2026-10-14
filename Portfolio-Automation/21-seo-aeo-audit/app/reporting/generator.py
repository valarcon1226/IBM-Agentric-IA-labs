"""Report generation combining SEO, AEO, and Lighthouse audit metrics."""

import os
from datetime import datetime
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader

SEVERITY_ORDER = {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4,
}

TEXTS = {
    "es": {
        "page_title": "Auditoría SEO & AEO de Alto Impacto",
        "badge_text": "Informe Confidencial para Clientes",
        "report_title": "Auditoría SEO & AEO (Optimización para Buscadores e IA)",
        "target_label": "Sitio Web Auditado",
        "pages_crawled_label": "Páginas Analizadas",
        "global_score_label": "Puntaje Global",
        "global_score_sub": "Rendimiento Integral",
        "seo_score_label": "SEO On-Page & Técnico",
        "seo_score_sub": "Visibilidad en Google",
        "aeo_score_label": "AEO (Respuestas IA)",
        "aeo_score_sub": "ChatGPT / Perplexity / Gemini",
        "executive_summary_title": "Resumen Ejecutivo de Negocio",
        "summary_source_tag": "Fuente del resumen",
        "aeo_details_title": "Desglose AEO: Preparación para Motores de IA",
        "aeo_desc": "Evaluación de la capacidad del sitio para ser citado y seleccionado como fuente preferida por asistentes de inteligencia artificial (SearchGPT, Perplexity, Google Overviews).",
        "criterion_label": "Criterio AEO",
        "analysis_label": "Diagnóstico Detectado",
        "score_label": "Puntos",
        "issues_title": "Oportunidades de Mejora Ordenadas por Impacto",
        "category_label": "Categoría",
        "how_to_fix_label": "Cómo solucionarlo paso a paso",
        "no_issues_message": "¡Excelente trabajo! No se detectaron problemas críticos ni advertencias.",
        "good_points_title": "Fortalezas Detectadas (Lo que está bien)",
        "crawled_pages_title": "Inventario de Páginas Rastreadas",
        "footer_text": "Auditoría generada automáticamente en 60 segundos",
    },
    "en": {
        "page_title": "High-Impact SEO & AEO Audit",
        "badge_text": "Client Confidential Report",
        "report_title": "SEO & AEO Audit (Search & AI Engine Optimization)",
        "target_label": "Audited Website",
        "pages_crawled_label": "Analyzed Pages",
        "global_score_label": "Overall Score",
        "global_score_sub": "Comprehensive Performance",
        "seo_score_label": "SEO On-Page & Technical",
        "seo_score_sub": "Google Visibility",
        "aeo_score_label": "AEO (AI Answers)",
        "aeo_score_sub": "ChatGPT / Perplexity / Gemini",
        "executive_summary_title": "Executive Business Summary",
        "summary_source_tag": "Summary Source",
        "aeo_details_title": "AEO Breakdown: AI Engine Readiness",
        "aeo_desc": "Assessment of how effectively AI search engines can retrieve, cite, and recommend your website.",
        "criterion_label": "AEO Criterion",
        "analysis_label": "Diagnosis",
        "score_label": "Score",
        "issues_title": "Actionable Issues Ordered by Impact",
        "category_label": "Category",
        "how_to_fix_label": "How to fix it step by step",
        "no_issues_message": "Great job! No critical issues or warnings detected.",
        "good_points_title": "Key Strengths (What is working well)",
        "crawled_pages_title": "Crawled Pages Inventory",
        "footer_text": "Audit automatically generated in 60 seconds",
    },
}


def calculate_seo_score(issues: list[dict[str, Any]]) -> int:
    """Calculate 0-100 SEO score based on issue severity penalties."""
    score = 100
    for issue in issues:
        sev = issue.get("severity", "LOW")
        if sev == "CRITICAL":
            score -= 15
        elif sev == "HIGH":
            score -= 10
        elif sev == "MEDIUM":
            score -= 5
        elif sev == "LOW":
            score -= 2
    return max(0, min(100, score))


def generate_template_executive_summary(
    url: str,
    overall_score: int,
    seo_score: int,
    aeo_score: int,
    top_issues: list[dict[str, Any]],
    lang: str = "es",
) -> str:
    """Generate dynamic, persuasive executive summary based on audit metrics."""
    if lang == "es":
        status_text = (
            "cuenta con una base sólida pero presenta oportunidades clave de mejora"
            if overall_score >= 70
            else "presenta barreras técnicas significativas que limitan su captación de clientes e indexación en buscadores e inteligencia artificial"
        )

        critical_count = sum(1 for i in top_issues if i.get("severity") in ("CRITICAL", "HIGH"))
        priority_lines = []
        for idx, iss in enumerate(top_issues[:3], 1):
            priority_lines.append(f"• Prioridad {idx} ({iss.get('category')}): {iss.get('message')} - Solución: {iss.get('fix')}")

        priorities_block = "\n".join(priority_lines) if priority_lines else "• Mantener la vigilancia y monitorización periódica de enlaces y contenido."

        return (
            f"El sitio web {url} obtiene un puntaje general de {overall_score}/100 (SEO Técnico: {seo_score}/100, AEO para IA: {aeo_score}/100). "
            f"El diagnóstico indica que la propiedad digital {status_text}.\n\n"
            f"Actualmente se han detectado {critical_count} puntos de impacto alto o crítico. "
            f"En el nuevo ecosistema donde los usuarios buscan tanto en Google como en asistentes de IA (ChatGPT, Perplexity, Gemini), "
            f"optimizar la estructura de datos, jerarquía de encabezados y respuestas concisas es fundamental para no perder clientes frente a la competencia.\n\n"
            f"Plan de acción inmediato recomendado:\n{priorities_block}"
        )
    else:
        status_text = (
            "has a solid foundation but significant optimization headroom"
            if overall_score >= 70
            else "has notable technical barriers hindering lead generation and AI engine discoverability"
        )
        priority_lines = []
        for idx, iss in enumerate(top_issues[:3], 1):
            priority_lines.append(f"• Priority {idx} ({iss.get('category')}): {iss.get('message')} - Solution: {iss.get('fix')}")
        priorities_block = "\n".join(priority_lines) if priority_lines else "• Continue regular monitoring of crawlability and content."

        return (
            f"The website {url} scored {overall_score}/100 (Technical SEO: {seo_score}/100, AEO for AI: {aeo_score}/100). "
            f"The diagnostic reveals that the digital asset {status_text}.\n\n"
            f"Recommended immediate priorities:\n{priorities_block}"
        )


def fetch_llm_executive_summary(
    url: str,
    overall_score: int,
    seo_score: int,
    aeo_score: int,
    top_issues: list[dict[str, Any]],
    lang: str = "es",
) -> tuple[str, str]:
    """Attempt to query a local LLM (e.g. Ollama) or fallback to dynamic template."""
    prompt = (
        f"Actúa como un consultor senior de SEO y AEO. Redacta un resumen ejecutivo de 3 párrafos para el cliente dueño de {url}.\n"
        f"Puntajes: Global {overall_score}/100, SEO {seo_score}/100, AEO {aeo_score}/100.\n"
        f"Problemas principales: {', '.join(i.get('message', '') for i in top_issues[:4])}.\n"
        f"Idioma: {lang}. Tono comercial, empático y orientado a ROI y captación de clientes."
    )

    try:
        # Try local Ollama instance if available
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                body = resp.json()
                response_text = body.get("response", "").strip()
                if response_text:
                    return response_text, "LLM Local (Ollama)"
    except Exception:
        pass

    summary = generate_template_executive_summary(
        url, overall_score, seo_score, aeo_score, top_issues, lang
    )
    return summary, "Plantilla Dinámica de Consultoría"


def build_audit_report(
    target_url: str,
    crawler_result: dict[str, Any],
    page_analyses: list[dict[str, Any]],
    site_analysis: dict[str, Any],
    aeo_analysis: dict[str, Any],
    lighthouse_result: dict[str, Any],
    lang: str = "es",
) -> dict[str, Any]:
    """Combine all audit sources into a unified report model."""
    lang = lang if lang in TEXTS else "es"
    t = TEXTS[lang]

    # Consolidate issues
    all_issues: list[dict[str, Any]] = []
    for p in page_analyses:
        all_issues.extend(p.get("issues", []))
    all_issues.extend(site_analysis.get("issues", []))
    all_issues.extend(aeo_analysis.get("issues", []))

    # Sort issues by severity
    all_issues.sort(key=lambda x: SEVERITY_ORDER.get(x.get("severity", "LOW"), 99))

    # Consolidate good points
    all_good_points: list[str] = []
    for p in page_analyses:
        all_good_points.extend(p.get("good_points", []))
    all_good_points.extend(site_analysis.get("good_points", []))
    all_good_points.extend(aeo_analysis.get("good_points", []))
    all_good_points = sorted(list(set(all_good_points)))

    # Compute scores
    seo_score = calculate_seo_score(all_issues)
    aeo_score = aeo_analysis.get("score", 0)

    if lighthouse_result.get("available"):
        lh_perf = lighthouse_result.get("performance") or 0
        lh_a11y = lighthouse_result.get("accessibility") or 0
        lh_bp = lighthouse_result.get("best_practices") or 0
        lh_seo = lighthouse_result.get("seo") or 0
        lh_avg = round((lh_perf + lh_a11y + lh_bp + lh_seo) / 4)
        overall_score = round(0.40 * seo_score + 0.40 * aeo_score + 0.20 * lh_avg)
    else:
        overall_score = round(0.50 * seo_score + 0.50 * aeo_score)

    overall_score = max(0, min(100, overall_score))

    summary_text, summary_src = fetch_llm_executive_summary(
        target_url, overall_score, seo_score, aeo_score, all_issues, lang=lang
    )

    def get_score_class(val: int) -> str:
        if val >= 85:
            return "score-green"
        if val >= 60:
            return "score-yellow"
        return "score-red"

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("report.html")

    pages_summary = []
    for pa in page_analyses:
        pages_summary.append({
            "url": pa.get("url"),
            "status_code": 200,
            "response_time_ms": next((p.get("response_time_ms", 0) for p in crawler_result.get("pages", []) if p.get("url") == pa.get("url")), 0),
            "title": pa.get("title"),
            "h1": pa.get("h1"),
            "json_ld_types": pa.get("json_ld_types"),
        })

    rendered_html = template.render(
        lang=lang,
        t=t,
        target_url=target_url,
        date_str=datetime.now().strftime("%Y-%m-%d %H:%M"),
        pages_count=len(page_analyses),
        overall_score=overall_score,
        seo_score=seo_score,
        aeo_score=aeo_score,
        lighthouse=lighthouse_result,
        executive_summary=summary_text,
        summary_source=summary_src,
        aeo=aeo_analysis,
        all_issues=all_issues,
        all_good_points=all_good_points,
        pages=pages_summary,
        get_score_class=get_score_class,
    )

    return {
        "target_url": target_url,
        "date": datetime.now().isoformat(),
        "overall_score": overall_score,
        "seo_score": seo_score,
        "aeo_score": aeo_score,
        "lighthouse": lighthouse_result,
        "executive_summary": summary_text,
        "summary_source": summary_src,
        "issues_count": len(all_issues),
        "issues": all_issues,
        "good_points": all_good_points,
        "pages_analyzed": len(page_analyses),
        "html_report": rendered_html,
    }
