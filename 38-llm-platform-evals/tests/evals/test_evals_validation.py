"""Unit tests for evals golden set validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.validate import (
    GoldenValidationError,
    validate_golden_dataset,
    validate_item,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
GOLDEN_PATH = PROJECT_DIR / "evals" / "golden.jsonl"
CORPUS_DIR = PROJECT_DIR / "corpus" / "markdown"


def test_golden_dataset_full_mode() -> None:
    """The committed 150-item golden set passes every validation rule of the protocol."""
    summary = validate_golden_dataset(GOLDEN_PATH, CORPUS_DIR, mode="full")
    assert summary["status"] == "VALID"
    assert summary["total_items"] == 150
    assert summary["answerable_total"] == 116
    assert summary["unanswerable_total"] == 34
    assert summary["dev_split"]["total"] == 30
    assert summary["test_split"]["total"] == 120


def test_validate_item_invalid_split() -> None:
    """Verifies that an item with an unsupported split triggers a validation error."""
    seen: set[str] = set()
    bad_item = {
        "id": "ERR-001",
        "split": "validation",
        "question": "Sample question?",
        "answerable": False,
        "gold_doc_paths": [],
        "key_fact_regexes": [],
    }
    errors = validate_item(bad_item, 1, seen)
    assert any("'split' must be 'dev' or 'test'" in err for err in errors)


def test_validate_item_malformed_regex() -> None:
    """Verifies that uncompilable regular expressions trigger validation errors."""
    seen: set[str] = set()
    bad_item = {
        "id": "ERR-002",
        "split": "dev",
        "question": "What is a Pod?",
        "answerable": True,
        "gold_doc_paths": ["architecture/nodes.md"],
        "key_fact_regexes": ["[unclosed bracket"],
    }
    errors = validate_item(bad_item, 1, seen)
    assert any("failed to compile" in err for err in errors)


def test_validate_item_answerable_without_gold_path() -> None:
    """Verifies that answerable items must provide at least one ground-truth path."""
    seen: set[str] = set()
    bad_item = {
        "id": "ERR-003",
        "split": "dev",
        "question": "What is a Node?",
        "answerable": True,
        "gold_doc_paths": [],
        "key_fact_regexes": ["kubelet"],
    }
    errors = validate_item(bad_item, 1, seen)
    assert any("must have at least one gold_doc_path" in err for err in errors)


def test_validate_item_unanswerable_with_gold_paths() -> None:
    """Verifies that unanswerable items must have empty gold_doc_paths."""
    seen: set[str] = set()
    bad_item = {
        "id": "ERR-004",
        "split": "test",
        "question": "How to make lasagna?",
        "answerable": False,
        "gold_doc_paths": ["architecture/nodes.md"],
        "key_fact_regexes": [],
    }
    errors = validate_item(bad_item, 1, seen)
    assert any("Unanswerable item must have empty gold_doc_paths" in err for err in errors)


def test_full_mode_fails_on_partial_set(tmp_path: Path) -> None:
    """Verifies that full mode validation fails when presented with fewer than 150 items."""
    partial_file = tmp_path / "partial.jsonl"
    first_twenty = GOLDEN_PATH.read_text(encoding="utf-8").splitlines()[:20]
    partial_file.write_text("\n".join(first_twenty) + "\n", encoding="utf-8")

    with pytest.raises(GoldenValidationError) as exc_info:
        validate_golden_dataset(partial_file, mode="full")
    assert "Full set check" in str(exc_info.value)
