"""Tests for TestCaseGenerator prompt construction, validation, and retry logic."""

from __future__ import annotations

from app.generator import TestCaseGenerator, extract_json
from app.llm import StubLLM
from app.models import AcceptanceCriterion, Requirement


def test_extract_json_markdown_blocks() -> None:
    raw = "```json\n{\"test_cases\": []}\n```"
    parsed = extract_json(raw)
    assert parsed == {"test_cases": []}


def test_generator_valid_on_first_try() -> None:
    req = Requirement(
        id="REQ-01",
        title="Autenticación de usuarios",
        description="Login básico",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Login exitoso"),
            AcceptanceCriterion(id="AC-02", text="Bloqueo tras 5 intentos"),
        ],
    )
    generator = TestCaseGenerator()
    llm = StubLLM(invalid_first=False)

    result = generator.generate(req, llm)

    assert result.requirement_id == "REQ-01"
    assert result.valid_on_first_try is True
    assert result.retries_used == 0
    assert result.error is None
    assert len(result.test_cases) > 0
    assert generator.invalid_responses_count == 0


def test_generator_retry_on_invalid_response() -> None:
    # First response is invalid; generator must trigger exactly ONE retry
    req = Requirement(
        id="REQ-02",
        title="Registro de clientes",
        description="Registro básico",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Correo válido"),
        ],
    )
    generator = TestCaseGenerator()
    llm = StubLLM(invalid_first=True)

    result = generator.generate(req, llm)

    # Validated on retry, NOT first try
    assert result.valid_on_first_try is False
    assert result.retries_used == 1
    assert result.error is None
    assert len(result.test_cases) > 0
    assert generator.invalid_responses_count == 1
    assert llm.call_count == 2


def test_generator_fails_after_retry() -> None:
    # Both initial call and retry fail
    req = Requirement(
        id="REQ-03",
        title="Búsqueda",
        description="Falla continua",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="Query")],
    )
    generator = TestCaseGenerator()
    llm = StubLLM(always_fail=True)

    result = generator.generate(req, llm)

    assert result.valid_on_first_try is False
    assert result.retries_used == 1
    assert len(result.test_cases) == 0
    assert result.error is not None
    assert generator.invalid_responses_count == 2
    assert llm.call_count == 2
