"""Deterministic evaluation metrics for test case generation using only the standard library."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def _to_dict(obj: Any) -> dict[str, Any]:
    """Helper to convert Pydantic models or dict-like objects into standard dictionaries."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return {}


def schema_valid_rate(results: list[Any]) -> float:
    """Calculate the rate of responses that validated on the first attempt.

    Formula: respuestas que validaron al primer intento / total de requisitos evaluados.
    """
    if not results:
        return 0.0
    valid_first = sum(1 for r in results if _to_dict(r).get("valid_on_first_try", False))
    return valid_first / len(results)


def declared_coverage(requirements: list[Any], test_cases_by_req: dict[str, list[Any]]) -> float:
    """Calculate the proportion of acceptance criteria cited in covers by at least one test case.

    Formula: criterios citados en covers por al menos un caso / total de criterios.
    """
    req_dicts = [_to_dict(r) for r in requirements]
    total_criteria = sum(len(r.get("acceptance_criteria", [])) for r in req_dicts)
    if total_criteria == 0:
        return 0.0

    covered_criteria_count = 0
    for req in req_dicts:
        req_id = req.get("id", "")
        valid_criteria_ids = {ac.get("id") for ac in req.get("acceptance_criteria", [])}
        cases = [_to_dict(tc) for tc in test_cases_by_req.get(req_id, [])]

        cited_for_req: set[str] = set()
        for tc in cases:
            for cid in tc.get("covers", []):
                if cid in valid_criteria_ids:
                    cited_for_req.add(cid)
        covered_criteria_count += len(cited_for_req)

    return covered_criteria_count / total_criteria


def verified_coverage(requirements: list[Any], test_cases_by_req: dict[str, list[Any]]) -> float:
    """Calculate the proportion of criteria verified by must_have regular expressions.

    Formula: criterios donde algun caso que lo cita cumple alguna expresion de must_have / total.
    """
    req_dicts = [_to_dict(r) for r in requirements]
    total_criteria = sum(len(r.get("acceptance_criteria", [])) for r in req_dicts)
    if total_criteria == 0:
        return 0.0

    verified_count = 0
    for req in req_dicts:
        req_id = req.get("id", "")
        cases = [_to_dict(tc) for tc in test_cases_by_req.get(req_id, [])]

        for ac in req.get("acceptance_criteria", []):
            ac_id = ac.get("id")
            must_have = ac.get("must_have", [])

            # Check if any test case citing this AC matches any regex in must_have
            is_verified = False
            for tc in cases:
                if ac_id not in tc.get("covers", []):
                    continue

                if not must_have:
                    # If no must_have regex defined, citation is accepted
                    is_verified = True
                    break

                # Combine title, steps and expected into a search corpus
                title = tc.get("title", "")
                steps = "\n".join(tc.get("steps", []))
                expected = tc.get("expected", "")
                corpus = f"{title}\n{steps}\n{expected}"

                if any(re.search(pat, corpus, re.IGNORECASE) for pat in must_have):
                    is_verified = True
                    break

            if is_verified:
                verified_count += 1

    return verified_count / total_criteria


def hallucinated_refs(requirements: list[Any], test_cases_by_req: dict[str, list[Any]]) -> float:
    """Calculate the rate of test cases citing acceptance criteria IDs that do not exist.

    Formula: casos que citan un id de criterio que no existe / total de casos.
    """
    req_dicts = [_to_dict(r) for r in requirements]
    all_cases: list[dict[str, Any]] = []
    hallucinated_count = 0

    for req in req_dicts:
        req_id = req.get("id", "")
        valid_criteria_ids = {ac.get("id") for ac in req.get("acceptance_criteria", [])}
        cases = [_to_dict(tc) for tc in test_cases_by_req.get(req_id, [])]
        all_cases.extend(cases)

        for tc in cases:
            covers = tc.get("covers", [])
            has_hallucinated = any(cid not in valid_criteria_ids for cid in covers)
            if has_hallucinated:
                hallucinated_count += 1

    if not all_cases:
        return 0.0
    return hallucinated_count / len(all_cases)


def duplicate_rate(
    requirements: list[Any],
    test_cases_by_req: dict[str, list[Any]],
    similarity_threshold: float = 0.9,
) -> float:
    """Calculate the proportion of duplicate test case pairs within requirements.

    Formula: pares de casos del mismo requisito con similitud difflib >= 0.9 en titulo+pasos / total de casos.
    """
    req_dicts = [_to_dict(r) for r in requirements]
    total_cases = sum(len(test_cases_by_req.get(req.get("id", ""), [])) for req in req_dicts)
    if total_cases == 0:
        return 0.0

    duplicate_pairs = 0
    for req in req_dicts:
        req_id = req.get("id", "")
        cases = [_to_dict(tc) for tc in test_cases_by_req.get(req_id, [])]
        num_cases = len(cases)
        for i in range(num_cases):
            text_i = f"{cases[i].get('title', '')}\n" + "\n".join(cases[i].get("steps", []))
            for j in range(i + 1, num_cases):
                text_j = f"{cases[j].get('title', '')}\n" + "\n".join(cases[j].get("steps", []))
                similarity = SequenceMatcher(None, text_i, text_j).ratio()
                if similarity >= similarity_threshold:
                    duplicate_pairs += 1

    return duplicate_pairs / total_cases


def negative_presence(requirements: list[Any], test_cases_by_req: dict[str, list[Any]]) -> float:
    """Calculate the proportion of requirements with at least one negative or edge test case.

    Formula: requisitos con al menos un caso negative o edge / total de requisitos.
    """
    req_dicts = [_to_dict(r) for r in requirements]
    if not req_dicts:
        return 0.0

    reqs_with_negative_or_edge = 0
    for req in req_dicts:
        req_id = req.get("id", "")
        cases = [_to_dict(tc) for tc in test_cases_by_req.get(req_id, [])]
        has_negative_or_edge = any(
            tc.get("level") in ("negative", "edge") for tc in cases
        )
        if has_negative_or_edge:
            reqs_with_negative_or_edge += 1

    return reqs_with_negative_or_edge / len(req_dicts)
