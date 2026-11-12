"""Validation script for evaluation golden dataset (evals/golden.jsonl).

Validates schema adherence, document path existence in the corpus, and regular expression
compilation. Supports validating the draft 20-item example set or the frozen 150-item full set.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validator")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DEFAULT_GOLDEN_PATH = PROJECT_DIR / "evals" / "golden.jsonl"
DEFAULT_CORPUS_DIR = PROJECT_DIR / "corpus" / "markdown"


class GoldenValidationError(Exception):
    """Raised when validation of golden dataset fails."""


def validate_item(
    item: dict[str, Any],
    line_number: int,
    seen_ids: set[str],
    corpus_dir: Path | None = None,
) -> list[str]:
    """Validates an individual item from the golden dataset.

    Returns a list of error message strings (empty if valid).
    """
    errors: list[str] = []
    required_fields = {
        "id": str,
        "split": str,
        "question": str,
        "answerable": bool,
        "gold_doc_paths": list,
        "key_fact_regexes": list,
    }

    for field, expected_type in required_fields.items():
        if field not in item:
            errors.append(f"Line {line_number}: Missing required field '{field}'")
        elif not isinstance(item[field], expected_type):
            errors.append(
                f"Line {line_number}: Field '{field}' must be {expected_type.__name__}, "
                f"got {type(item[field]).__name__}"
            )

    if errors:
        return errors

    item_id = item["id"].strip()
    if not item_id:
        errors.append(f"Line {line_number}: 'id' cannot be empty")
    elif item_id in seen_ids:
        errors.append(f"Line {line_number}: Duplicate id '{item_id}'")
    else:
        seen_ids.add(item_id)

    split = item["split"].strip().lower()
    if split not in ("dev", "test"):
        errors.append(
            f"Line {line_number} (id: {item_id}): 'split' must be 'dev' or 'test', got '{split}'"
        )

    question = item["question"].strip()
    if not question:
        errors.append(f"Line {line_number} (id: {item_id}): 'question' cannot be empty")

    answerable = item["answerable"]
    gold_paths = item["gold_doc_paths"]
    regexes = item["key_fact_regexes"]

    if answerable:
        if not gold_paths:
            errors.append(
                f"Line {line_number} (id: {item_id}): "
                "Answerable item must have at least one gold_doc_path"
            )
        if not regexes:
            errors.append(
                f"Line {line_number} (id: {item_id}): "
                "Answerable item must have at least one key_fact_regex"
            )

        if corpus_dir and corpus_dir.exists():
            for p in gold_paths:
                if not isinstance(p, str) or not p.strip():
                    errors.append(
                        f"Line {line_number} (id: {item_id}): Invalid path entry: '{p}'"
                    )
                    continue
                clean_rel_path = p.strip().lstrip("/\\")
                full_path = corpus_dir / clean_rel_path
                if not full_path.exists():
                    errors.append(
                        f"Line {line_number} (id: {item_id}): "
                        f"Gold doc path does not exist in corpus: '{clean_rel_path}'"
                    )
    else:
        if gold_paths:
            errors.append(
                f"Line {line_number} (id: {item_id}): "
                f"Unanswerable item must have empty gold_doc_paths, got {gold_paths}"
            )

    for idx, pat in enumerate(regexes):
        if not isinstance(pat, str):
            errors.append(
                f"Line {line_number} (id: {item_id}): regex index {idx} must be string"
            )
            continue
        try:
            re.compile(pat)
        except re.error as e:
            errors.append(
                f"Line {line_number} (id: {item_id}): Regex '{pat}' failed to compile: {e}"
            )

    return errors


def validate_golden_dataset(
    golden_path: Path,
    corpus_dir: Path | None = None,
    mode: str = "auto",
) -> dict[str, Any]:
    """Validates the complete golden dataset file.

    Args:
        golden_path: Path to evals/golden.jsonl.
        corpus_dir: Directory containing plain markdown corpus files.
        mode: "auto", "examples", or "full".

    Returns:
        Summary dict containing counts and verification details.

    Raises:
        GoldenValidationError: If any schema, count, path, or regex validation fails.
    """
    if not golden_path.exists():
        raise GoldenValidationError(f"Golden dataset file does not exist: {golden_path}")

    lines = golden_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        raise GoldenValidationError(f"Golden dataset file is empty: {golden_path}")

    all_errors: list[str] = []
    seen_ids: set[str] = set()

    dev_ans = 0
    dev_unans = 0
    test_ans = 0
    test_unans = 0

    for idx, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            all_errors.append(f"Line {idx}: Invalid JSON syntax: {e}")
            continue

        item_errors = validate_item(item, idx, seen_ids, corpus_dir)
        all_errors.extend(item_errors)

        if not item_errors:
            split = item["split"].strip().lower()
            ans = item["answerable"]
            if split == "dev":
                if ans:
                    dev_ans += 1
                else:
                    dev_unans += 1
            elif split == "test":
                if ans:
                    test_ans += 1
                else:
                    test_unans += 1

    total_items = len(seen_ids)
    effective_mode = mode
    if effective_mode == "auto":
        effective_mode = "full" if total_items >= 100 else "examples"

    logger.info("Validation mode: %s (Total items parsed: %d)", effective_mode, total_items)
    logger.info("Counts: dev_answerable=%d, dev_unanswerable=%d", dev_ans, dev_unans)
    logger.info("Counts: test_answerable=%d, test_unanswerable=%d", test_ans, test_unans)

    if effective_mode == "full":
        expected_dev = 30
        expected_test_ans = 96
        expected_test_unans = 24
        expected_total = 150

        dev_total = dev_ans + dev_unans
        if dev_total != expected_dev:
            all_errors.append(
                f"Full set check: Expected {expected_dev} dev items, got {dev_total}"
            )
        if test_ans != expected_test_ans:
            all_errors.append(
                f"Full set check: Expected {expected_test_ans} test answerable, got {test_ans}"
            )
        if test_unans != expected_test_unans:
            all_errors.append(
                f"Full set check: Expected {expected_test_unans} test unans, got {test_unans}"
            )
        if total_items != expected_total:
            all_errors.append(
                f"Full set check: Expected {expected_total} total items, got {total_items}"
            )
    elif effective_mode == "examples":
        expected_examples = 20
        expected_ans = 10
        expected_unans = 10
        total_ans = dev_ans + test_ans
        total_unans = dev_unans + test_unans

        if total_items != expected_examples:
            all_errors.append(
                f"Example set check: Expected {expected_examples} items, got {total_items}"
            )
        if total_ans != expected_ans:
            all_errors.append(
                f"Example set check: Expected {expected_ans} answerable items, got {total_ans}"
            )
        if total_unans != expected_unans:
            all_errors.append(
                f"Example set check: Expected {expected_unans} unanswerable, got {total_unans}"
            )

    if all_errors:
        error_summary = "\n".join(f" - {err}" for err in all_errors)
        logger.error(
            "Golden dataset validation failed with %d errors:\n%s",
            len(all_errors),
            error_summary,
        )
        raise GoldenValidationError(
            f"Golden dataset validation failed with {len(all_errors)} errors:\n{error_summary}"
        )

    summary = {
        "status": "VALID",
        "file": str(golden_path),
        "mode": effective_mode,
        "total_items": total_items,
        "dev_split": {
            "total": dev_ans + dev_unans,
            "answerable": dev_ans,
            "unanswerable": dev_unans,
        },
        "test_split": {
            "total": test_ans + test_unans,
            "answerable": test_ans,
            "unanswerable": test_unans,
        },
        "answerable_total": dev_ans + test_ans,
        "unanswerable_total": dev_unans + test_unans,
    }
    logger.info("All golden dataset checks PASSED successfully.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate evals/golden.jsonl schema, counts, corpus paths, and regexes."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_GOLDEN_PATH,
        help="Path to golden.jsonl file.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="Path to plain markdown corpus directory.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Enforce full 150-item counts (30 dev, 96 test answerable, 24 test unanswerable).",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Enforce 20-item example set counts (10 answerable, 10 unanswerable).",
    )
    args = parser.parse_args()

    mode = "auto"
    if args.full:
        mode = "full"
    elif args.examples:
        mode = "examples"

    try:
        summary = validate_golden_dataset(args.file, args.corpus_dir, mode=mode)
        print(json.dumps(summary, indent=2))
        sys.exit(0)
    except GoldenValidationError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
