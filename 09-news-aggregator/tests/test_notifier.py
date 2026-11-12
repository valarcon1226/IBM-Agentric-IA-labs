"""Unit tests for Jinja2 digest template rendering and SMTP notifications."""

from unittest.mock import MagicMock, patch

from delivery.notifier import render_digest_html, send_digest_email


def test_render_digest_html():
    clustered = {
        "Inteligencia Artificial": [
            {
                "title": "OpenAI presenta su nuevo modelo GPT-5",
                "url": "https://example.com/gpt5",
                "source_name": "TechNews A",
                "published_date": "14/10/2026",
                "ai_summary": "- Modelo con razonamiento avanzado.\n- Supera benchmarks clave.",
                "duplicates": [
                    {"url": "https://dailytech.local/gpt5-b", "source_name": "DailyTech B"},
                ],
            }
        ]
    }

    html = render_digest_html(
        target_audience="EQUIPO_TECNOLOGIA",
        clustered_articles=clustered,
        digest_date="14/10/2026 10:00 UTC",
    )

    assert "Boletín Diario de Inteligencia" in html
    assert "EQUIPO_TECNOLOGIA" in html
    assert "Inteligencia Artificial" in html
    assert "OpenAI presenta su nuevo modelo GPT-5" in html
    assert "https://example.com/gpt5" in html
    assert "DailyTech B" in html
    assert "Otras fuentes con cobertura similar" in html


def test_send_digest_email_success():
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_instance = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_instance

        success = send_digest_email(
            smtp_host="localhost",
            smtp_port=1025,
            from_email="intel@news.local",
            to_email="briefing@example.com",
            subject="Boletín de Prueba",
            html_body="<html><body>Hola</body></html>",
        )

        assert success is True
        mock_instance.sendmail.assert_called_once()
        args = mock_instance.sendmail.call_args[0]
        assert args[0] == "intel@news.local"
        assert args[1] == ["briefing@example.com"]


def test_send_digest_email_failure():
    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("SMTP server down")):
        success = send_digest_email(
            smtp_host="localhost",
            smtp_port=1025,
            from_email="intel@news.local",
            to_email="briefing@example.com",
            subject="Boletín de Prueba",
            html_body="<html><body>Hola</body></html>",
        )
        assert success is False
