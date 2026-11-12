import pytest

from app.templating import (
    TemplateRenderError,
    available_templates,
    email_subject,
    render_html_template,
    render_template,
)


def test_available_templates_lists_text_only():
    templates = available_templates()
    assert templates == ["daily_report", "slack_alert", "welcome_email"]


def test_render_welcome_email_ok():
    text = render_template(
        "welcome_email", {"user_name": "Alice", "system": "Data Intake Pipeline"}
    )
    assert "Hello Alice" in text
    assert "Data Intake Pipeline" in text


def test_render_slack_alert_ok():
    text = render_template(
        "slack_alert", {"severity": "critical", "message": "disk full", "system": "db-1"}
    )
    assert "critical" in text
    assert "disk full" in text


def test_render_daily_report_ok():
    text = render_template(
        "daily_report", {"report_date": "2024-01-01", "summary": "all good", "total_items": 42}
    )
    assert "2024-01-01" in text
    assert "42" in text


def test_render_missing_variable_raises():
    with pytest.raises(TemplateRenderError):
        render_template("welcome_email", {"user_name": "Alice"})  # missing "system"


def test_render_nonexistent_template_raises():
    with pytest.raises(TemplateRenderError):
        render_template("does_not_exist", {})


def test_render_html_template_optional():
    html = render_html_template("welcome_email", {"user_name": "Alice", "system": "Sys"})
    assert html is not None
    assert "<strong>Sys</strong>" in html


def test_render_html_template_missing_variant_returns_none():
    assert render_html_template("slack_alert", {}) is None


def test_render_html_template_autoescapes():
    html = render_html_template("welcome_email", {"user_name": "<script>", "system": "Sys"})
    assert "<script>" not in html


def test_email_subject_uses_payload_subject():
    assert email_subject("welcome_email", {"subject": "Custom Subject"}) == "Custom Subject"


def test_email_subject_falls_back_to_title_case_name():
    assert email_subject("welcome_email", {}) == "Welcome Email"
