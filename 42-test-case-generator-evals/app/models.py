"""Data models for requirements and generated test cases using Pydantic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AcceptanceCriterion(BaseModel):
    """Single acceptance criterion within a requirement."""

    id: str
    text: str
    must_have: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    """Specification of a feature requirement with acceptance criteria."""

    id: str
    title: str
    description: str
    split: Literal["dev", "test"] = "dev"
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)


class TestCase(BaseModel):
    """Generated test case for a given requirement."""

    __test__ = False

    id: str
    title: str
    level: Literal["smoke", "functional", "negative", "edge"]
    preconditions: str = ""
    steps: list[str] = Field(..., min_length=1)
    expected: str
    covers: list[str] = Field(default_factory=list)

    @field_validator("preconditions", mode="before")
    @classmethod
    def normalize_preconditions(cls, v: Any) -> str:
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        if v is None:
            return ""
        return str(v)

    @field_validator("steps", mode="before")
    @classmethod
    def validate_steps_not_empty(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            lines = [line.strip() for line in v.splitlines() if line.strip()]
            if lines:
                return lines
            return [v.strip()]
        if isinstance(v, list):
            cleaned = [str(item).strip() for item in v if str(item).strip()]
            if not cleaned:
                raise ValueError("steps list cannot be empty")
            return cleaned
        raise ValueError("steps must be a list of non-empty strings")


class GeneratedTestSuite(BaseModel):
    """Container for a list of generated test cases."""

    test_cases: list[TestCase] = Field(default_factory=list)


def parse_test_cases(payload: Any) -> list[TestCase]:
    """Parse and validate test cases from a dictionary or list payload."""
    if isinstance(payload, list):
        return [TestCase.model_validate(item) for item in payload]
    if isinstance(payload, dict):
        if "test_cases" in payload:
            suite = GeneratedTestSuite.model_validate(payload)
            return suite.test_cases
        if "cases" in payload:
            return [TestCase.model_validate(item) for item in payload["cases"]]
        # Maybe a single test case wrapped in a dict
        if "id" in payload and "title" in payload and "steps" in payload:
            return [TestCase.model_validate(payload)]
    raise ValueError(f"Unable to parse test cases from payload of type {type(payload).__name__}")
