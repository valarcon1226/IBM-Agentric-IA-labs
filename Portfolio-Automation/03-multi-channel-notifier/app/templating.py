from pathlib import Path
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    UndefinedError,
    select_autoescape,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Plain-text templates used by every channel. StrictUndefined (DECISIONES-03 N5): a missing
# variable raises instead of rendering blank/silent output.
_text_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

# HTML email bodies (optional `<name>.html.j2`), autoescaped.
_html_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    undefined=StrictUndefined,
    autoescape=select_autoescape(enabled_extensions=("j2",), default_for_string=True),
    trim_blocks=True,
    lstrip_blocks=True,
)


class TemplateRenderError(Exception):
    """Raised when a template name is unknown or a required variable is missing."""


def available_templates() -> list[str]:
    return sorted(
        p.name[: -len(".j2")] for p in TEMPLATES_DIR.glob("*.j2") if not p.name.endswith(".html.j2")
    )


def render_template(name: str, context: dict[str, Any]) -> str:
    try:
        template = _text_env.get_template(f"{name}.j2")
    except TemplateNotFound as exc:
        raise TemplateRenderError(f"Unknown template: {name}") from exc
    try:
        return template.render(**context)
    except UndefinedError as exc:
        raise TemplateRenderError(f"Missing template variable: {exc}") from exc


def render_html_template(name: str, context: dict[str, Any]) -> str | None:
    path = TEMPLATES_DIR / f"{name}.html.j2"
    if not path.exists():
        return None
    try:
        template = _html_env.get_template(f"{name}.html.j2")
    except TemplateNotFound as exc:
        raise TemplateRenderError(f"Unknown template: {name}") from exc
    try:
        return template.render(**context)
    except UndefinedError as exc:
        raise TemplateRenderError(f"Missing template variable: {exc}") from exc


def email_subject(name: str, context: dict[str, Any]) -> str:
    subject = context.get("subject")
    if subject:
        # Defense in depth: app.models already rejects CR/LF in payload["subject"] with a 422
        # before this is ever reached, but strip here too so this helper can never produce a
        # header-injecting value on its own.
        return str(subject).replace("\r", "").replace("\n", "")
    return name.replace("_", " ").title()
