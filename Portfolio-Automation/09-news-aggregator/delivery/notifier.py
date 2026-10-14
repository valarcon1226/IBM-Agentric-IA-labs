"""Notification delivery module for compiling and dispatching email digests."""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_digest_html(
    target_audience: str,
    clustered_articles: dict[str, list[dict[str, Any]]],
    digest_date: str | None = None,
) -> str:
    """Renders the HTML email digest template using Jinja2."""
    if not digest_date:
        digest_date = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("email_digest.html")

    return template.render(
        target_audience=target_audience,
        clustered_articles=clustered_articles,
        digest_date=digest_date,
    )


def send_digest_email(
    smtp_host: str,
    smtp_port: int,
    from_email: str,
    to_email: str,
    subject: str,
    html_body: str,
    timeout: float = 10.0,
) -> bool:
    """Sends the formatted HTML digest via SMTP (e.g. to Mailpit or standard server)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    # Plaintext fallback part
    plain_text = f"Boletín de Inteligencia - {subject}\n\nPor favor visualice este correo con un cliente que soporte HTML."
    part_text = MIMEText(plain_text, "plain", "utf-8")
    part_html = MIMEText(html_body, "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            server.sendmail(from_email, [to_email], msg.as_string())
        logger.info(f"Digest email successfully dispatched to {to_email} via {smtp_host}:{smtp_port}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send email to {to_email} via {smtp_host}:{smtp_port}: {exc}")
        return False
