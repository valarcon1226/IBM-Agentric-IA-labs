"""Tests for AEO (Answer Engine Optimization) checks and 0-100 scoring."""

from app.checks.aeo import analyze_aeo, is_question_text


def test_is_question_text_detection():
    """Correctly identifies question headings in Spanish and English."""
    assert is_question_text("¿Qué tipos de café ofrecen?") is True
    assert is_question_text("¿Cómo realizar un pedido?") is True
    assert is_question_text("Dónde queda la cafetería?") is True
    assert is_question_text("Por qué elegir café de origen") is True
    assert is_question_text("What are your business hours?") is True
    assert is_question_text("How can I book a table?") is True

    assert is_question_text("Nuestra Historia y Misión") is False
    assert is_question_text("Menú Principal de Productos") is False


def test_perfect_page_aeo_score_100(perfect_html: str):
    """Page with question headings, concise answers, schema, and contact/hours gets full 100 score."""
    res = analyze_aeo(
        url="https://ejemplo.com/cafe-origen",
        html=perfect_html,
        json_ld_types=["LocalBusiness", "FAQPage"],
    )

    assert res["score"] == 100
    assert res["max_score"] == 100
    assert res["questions_count"] >= 2
    assert res["contact_info_detected"] is True
    assert res["hours_detected"] is True

    # Check 4 criteria breakdowns
    breakdown = {c["criterion"]: c["points"] for c in res["criteria_breakdown"]}
    assert breakdown["Preguntas como encabezados"] == 25
    assert breakdown["Respuestas concisas bajo cada pregunta"] == 25
    assert breakdown["Schema FAQ / HowTo / LocalBusiness"] == 25
    assert breakdown["Contacto y horarios legibles como texto"] == 25
    assert len(res["issues"]) == 0


def test_broken_page_aeo_low_score(broken_aeo_html: str):
    """Page lacking question headings, schema, and contact details receives low AEO score."""
    res = analyze_aeo(
        url="https://ejemplo.com/servicios",
        html=broken_aeo_html,
        json_ld_types=[],
    )

    assert res["score"] <= 20
    issue_codes = {i["code"] for i in res["issues"]}
    assert "AEO_NO_QUESTION_HEADINGS" in issue_codes
    assert "AEO_MISSING_TARGET_SCHEMA" in issue_codes
    assert "AEO_NO_CONTACT_HOURS_TEXT" in issue_codes
