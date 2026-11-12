import re

from pydantic import BaseModel


class Report(BaseModel):
    title: str
    findings: list[str]
    sources: list[str]
    recommendations: list[str]
    markdown: str
    llm_calls: int
    seconds: float


def _bullets(markdown: str, heading: re.Pattern) -> list[str]:
    """Bullets ("- x" / "1. x") under the first heading that matches, until the next heading."""
    out, inside = [], False
    for line in markdown.splitlines():
        if line.lstrip().startswith("#"):
            inside = bool(heading.search(line))
            continue
        m = re.match(r"\s*(?:[-*]|\d+\.)\s+(.*\S)", line)
        if inside and m:
            out.append(m.group(1))
    return out


def build_report(topic: str, markdown: str, sources: set[str], llm_calls: int, seconds: float) -> Report:
    """Same Report for both engines. The structure is parsed from the final Markdown instead of asking a
    small local model for JSON (which it often breaks)."""
    markdown = markdown.replace("TERMINATE", "").strip()
    return Report(
        title=topic,
        findings=_bullets(markdown, re.compile(r"hallazgo|finding", re.I)),
        sources=sorted(sources),
        recommendations=_bullets(markdown, re.compile(r"recomendaci|recommendation", re.I)),
        markdown=markdown,
        llm_calls=llm_calls,
        seconds=round(seconds, 2),
    )
