"""Test case generator module with prompt assembly, Pydantic validation and retry logic."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.llm import BaseLLM
from app.models import Requirement, TestCase, parse_test_cases


@dataclass
class GenerationResult:
    """Result of running test case generation on a single requirement."""

    requirement_id: str
    requirement_title: str
    test_cases: list[TestCase] = field(default_factory=list)
    raw_response: str = ""
    valid_on_first_try: bool = False
    retries_used: int = 0
    error: str | None = None


def extract_json(raw_text: str) -> Any:
    """Extract and parse JSON object or array from raw text, stripping markdown if present."""
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty response received from LLM")

    # Strip markdown code blocks
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # Sometimes LLM outputs leading/trailing text outside braces
    start_brace = text.find("{")
    start_bracket = text.find("[")

    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = text.rfind("}")
        if end_brace != -1 and end_brace > start_brace:
            text = text[start_brace : end_brace + 1]
    elif start_bracket != -1:
        end_bracket = text.rfind("]")
        if end_bracket != -1 and end_bracket > start_bracket:
            text = text[start_bracket : end_bracket + 1]

    return json.loads(text)


class TestCaseGenerator:
    """Orchestrates prompt assembly, LLM completion, validation, and single retry."""

    __test__ = False

    def __init__(self) -> None:
        self.invalid_responses_count: int = 0

    def build_prompt(self, requirement: Requirement) -> str:
        """Construct the generation prompt from a requirement definition."""
        criteria_lines = "\n".join(
            f"- [{ac.id}] {ac.text}" for ac in requirement.acceptance_criteria
        )
        return (
            f"Generate a comprehensive suite of test cases for the following requirement.\n\n"
            f"Requirement ID: {requirement.id}\n"
            f"Title: {requirement.title}\n"
            f"Description: {requirement.description}\n\n"
            f"Acceptance Criteria:\n{criteria_lines}\n\n"
            f"You must return ONLY a valid JSON object matching this exact schema:\n"
            f"{{\n"
            f'  "test_cases": [\n'
            f"    {{\n"
            f'      "id": "TC-01",\n'
            f'      "title": "Descriptive test case title",\n'
            f'      "level": "smoke" | "functional" | "negative" | "edge",\n'
            f'      "preconditions": "Preconditions or setup steps",\n'
            f'      "steps": ["Step 1", "Step 2"],\n'
            f'      "expected": "Expected behavior or result",\n'
            f'      "covers": ["AC-01"]\n'
            f"    }}\n"
            f"  ]\n"
            f"}}\n\n"
            f"Guidelines:\n"
            f"- 'level' must be strictly one of: 'smoke', 'functional', 'negative', 'edge'.\n"
            f"- 'steps' must be a non-empty list of strings.\n"
            f"- 'covers' must only contain valid Acceptance Criteria IDs from the list above.\n"
            f"- Include negative and edge cases covering failure scenarios and boundaries.\n"
            f"- Write every title, precondition, step and expected result in the language of the requirement.\n"
            f"- Output strictly raw JSON, no additional explanatory commentary."
        )

    def generate(self, requirement: Requirement, llm: BaseLLM) -> GenerationResult:
        """Generate test cases with validation and exactly one retry if invalid."""
        system_prompt = (
            "You are an expert QA automation engineer. "
            "You generate structured, high-quality test cases adhering strictly to JSON schemas."
        )
        prompt = self.build_prompt(requirement)

        # First attempt
        raw_response = ""
        try:
            raw_response = llm.complete(prompt, system_prompt=system_prompt)
            parsed_json = extract_json(raw_response)
            cases = parse_test_cases(parsed_json)
            return GenerationResult(
                requirement_id=requirement.id,
                requirement_title=requirement.title,
                test_cases=cases,
                raw_response=raw_response,
                valid_on_first_try=True,
                retries_used=0,
            )
        except Exception as first_err:
            self.invalid_responses_count += 1
            error_msg = f"{type(first_err).__name__}: {first_err}"

        # Exactly ONE retry with the error
        retry_prompt = (
            f"{prompt}\n\n"
            f"ATTENTION: Your previous response was INVALID and failed validation with error:\n"
            f"{error_msg}\n\n"
            f"Please correct the error and output ONLY the valid JSON object "
            f"adhering strictly to the schema."
        )

        try:
            raw_retry = llm.complete(retry_prompt, system_prompt=system_prompt)
            parsed_json = extract_json(raw_retry)
            cases = parse_test_cases(parsed_json)
            return GenerationResult(
                requirement_id=requirement.id,
                requirement_title=requirement.title,
                test_cases=cases,
                raw_response=raw_retry,
                valid_on_first_try=False,
                retries_used=1,
            )
        except Exception as second_err:
            self.invalid_responses_count += 1
            final_err = f"{type(second_err).__name__}: {second_err}"
            return GenerationResult(
                requirement_id=requirement.id,
                requirement_title=requirement.title,
                test_cases=[],
                raw_response=raw_response or getattr(locals(), "raw_retry", ""),
                valid_on_first_try=False,
                retries_used=1,
                error=final_err,
            )
