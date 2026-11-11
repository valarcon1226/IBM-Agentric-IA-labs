"""Tests for human review export and precision calculation tooling."""

from __future__ import annotations

import json
from pathlib import Path

from evals.review import export_review, score_review


def test_review_export_creates_file(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval.json"
    data = {
        "model": "test-model",
        "split": "dev",
        "requirements_results": [
            {
                "requirement_id": "REQ-01",
                "test_cases": [
                    {
                        "id": "TC-01",
                        "level": "smoke",
                        "title": "Login OK",
                        "steps": ["Step 1", "Step 2"],
                        "expected": "Redirect",
                        "covers": ["AC-01"],
                    }
                ],
            }
        ],
    }
    with open(eval_json, "w", encoding="utf-8") as f:
        json.dump(data, f)

    review_file = export_review("test-model", reports_dir=tmp_path)

    assert review_file.is_file()
    with open(review_file, encoding="utf-8") as f:
        content = f.read()
    assert "| Req ID | Case ID | Level | Title | Steps | Expected | Covers | Review (OK/wrong/edit) | Notes |" in content
    assert "| `REQ-01` | `TC-01` | `smoke` | Login OK | 1. Step 1<br>2. Step 2 | Redirect | AC-01 | | |" in content


def test_review_score_empty_reports_no_review(tmp_path: Path) -> None:
    # A review sheet with empty review cells must report NO review, not invent a score
    review_file = tmp_path / "review.md"
    content = (
        "| Req ID | Case ID | Level | Title | Steps | Expected | Covers | Review (OK/wrong/edit) | Notes |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |\n"
        "| `REQ-01` | `TC-01` | `smoke` | Title 1 | Steps | Expected | AC-01 | | |\n"
        "| `REQ-01` | `TC-02` | `functional` | Title 2 | Steps | Expected | AC-02 | | |\n"
    )
    with open(review_file, "w", encoding="utf-8") as f:
        f.write(content)

    score_result = score_review("test-model", reports_dir=tmp_path)
    assert score_result is None


def test_review_score_completed(tmp_path: Path) -> None:
    review_file = tmp_path / "review.md"
    content = (
        "| Req ID | Case ID | Level | Title | Steps | Expected | Covers | Review (OK/wrong/edit) | Notes |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |\n"
        "| `REQ-01` | `TC-01` | `smoke` | Title 1 | Steps | Expected | AC-01 | OK | Good |\n"
        "| `REQ-01` | `TC-02` | `functional` | Title 2 | Steps | Expected | AC-02 | OK | Good |\n"
        "| `REQ-01` | `TC-03` | `negative` | Title 3 | Steps | Expected | AC-03 | wrong | Bad |\n"
        "| `REQ-01` | `TC-04` | `edge` | Title 4 | Steps | Expected | AC-04 | edit | Minor edit |\n"
    )
    with open(review_file, "w", encoding="utf-8") as f:
        f.write(content)

    score_result = score_review("test-model", reports_dir=tmp_path)
    assert score_result is not None
    assert score_result["total_cases"] == 4
    assert score_result["total_reviewed"] == 4
    assert score_result["ok"] == 2
    assert score_result["wrong"] == 1
    assert score_result["edit"] == 1
    assert score_result["human_precision"] == 0.50
