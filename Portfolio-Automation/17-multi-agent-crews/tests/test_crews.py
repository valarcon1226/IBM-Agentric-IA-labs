"""Both engines run end to end against the fake LLM: tools are really called and the Report is complete."""

import pytest

from app.crews import autogen_team, crewai_crew
from app.models import build_report
from app.tools import calculate, search_corpus


@pytest.mark.parametrize("run", [crewai_crew.run, autogen_team.run], ids=["crewai", "autogen"])
def test_engine_produces_full_report(run):
    report = run("demanda de agentes de IA en LATAM")
    assert report.findings and report.recommendations
    assert report.sources and all(s.startswith("doc_") for s in report.sources)  # came from the search tool
    assert "## Hallazgos" in report.markdown and "TERMINATE" not in report.markdown
    assert report.llm_calls >= 4  # at least one model call per agent
    assert report.seconds >= 0


def test_search_ranks_by_shared_words_and_collects_sources():
    sources = set()
    out = search_corpus("vacantes CrewAI AutoGen", sources)
    assert out.startswith("[doc_03.md]")
    assert "doc_03.md" in sources and len(sources) <= 3
    assert search_corpus("zzzz qqqq") == "No documents matched the query."


@pytest.mark.parametrize("expr, expected", [("(3600-1200)/1200", "2.0"), ("-2*3+1", "-5"), ("10/4", "2.5")])
def test_calculate(expr, expected):
    assert calculate(expr) == expected


@pytest.mark.parametrize("expr", ["9**9**99", "__import__('os')", "2+", "1/0", "1" * 61])
def test_calculate_rejects_unsafe_or_invalid(expr):
    assert calculate(expr).startswith("Error")


def test_build_report_parses_sections():
    md = "# T\n\n## Hallazgos\n- a\n- b\n\n## Recomendaciones\n1. c\n\n## Fuentes\n- doc_01.md\nTERMINATE"
    r = build_report("t", md, {"doc_01.md"}, 5, 1.234)
    assert r.findings == ["a", "b"] and r.recommendations == ["c"] and r.seconds == 1.23
    assert "TERMINATE" not in r.markdown
