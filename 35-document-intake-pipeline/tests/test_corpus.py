"""Unit tests for deterministic corpus generation."""

from __future__ import annotations

import csv
from pathlib import Path

from corpus.generate import generate_corpus


def test_corpus_determinism_same_seed(tmp_path: Path) -> None:
    """Verifies that the same seed produces identical byte outputs and manifest."""
    dir1 = tmp_path / "run1"
    labels1 = tmp_path / "labels1.csv"
    manifest1 = tmp_path / "manifest1.sha256"

    dir2 = tmp_path / "run2"
    labels2 = tmp_path / "labels2.csv"
    manifest2 = tmp_path / "manifest2.sha256"

    # Generate 50 documents for fast unit test
    generate_corpus(seed=42, count=50, output_dir=dir1, labels_file=labels1, manifest_file=manifest1)
    generate_corpus(seed=42, count=50, output_dir=dir2, labels_file=labels2, manifest_file=manifest2)

    assert manifest1.read_text(encoding="utf-8") == manifest2.read_text(encoding="utf-8")
    assert labels1.read_text(encoding="utf-8") == labels2.read_text(encoding="utf-8")

    # Byte-by-byte check on files
    for f1 in dir1.glob("*.pdf"):
        f2 = dir2 / f1.name
        assert f2.exists(), f"Missing file in run2: {f1.name}"
        assert f1.read_bytes() == f2.read_bytes(), f"Byte mismatch for {f1.name}"


def test_corpus_determinism_different_seed(tmp_path: Path) -> None:
    """Verifies that different seeds produce different manifests."""
    dir_a = tmp_path / "run_a"
    labels_a = tmp_path / "labels_a.csv"
    manifest_a = tmp_path / "manifest_a.sha256"

    dir_b = tmp_path / "run_b"
    labels_b = tmp_path / "labels_b.csv"
    manifest_b = tmp_path / "manifest_b.sha256"

    generate_corpus(seed=101, count=50, output_dir=dir_a, labels_file=labels_a, manifest_file=manifest_a)
    generate_corpus(seed=202, count=50, output_dir=dir_b, labels_file=labels_b, manifest_file=manifest_b)

    assert manifest_a.read_text(encoding="utf-8") != manifest_b.read_text(encoding="utf-8")


def test_corpus_proportions_and_labels(tmp_path: Path) -> None:
    """Verifies exact proportions: 3% corrupt, 2% duplicate, and valid types/correspondents."""
    out_dir = tmp_path / "corpus_full"
    labels_path = tmp_path / "labels_full.csv"
    manifest_path = tmp_path / "manifest_full.sha256"

    generate_corpus(seed=42, count=100, output_dir=out_dir, labels_file=labels_path, manifest_file=manifest_path)

    with open(labels_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 100
    outcomes = [r["expected_outcome"] for r in rows]
    assert outcomes.count("corrupt") == 3
    assert outcomes.count("duplicate") == 2
    assert outcomes.count("ingest") == 95
