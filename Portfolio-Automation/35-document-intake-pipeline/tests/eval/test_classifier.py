"""Machine learning document classifier evaluation test suite.

Evaluates the Paperless-ngx automatic classifier across 3 distinct seeds on a pre-registered
stratified 500/100 train/test split. Computes metrics in pure Python (no sklearn dependency).

Cited source:
- Management command: src/documents/management/commands/document_create_classifier.py
- Matching algorithm: src/documents/models.py (MatchingModel.MATCH_AUTO = 6)
"""

from __future__ import annotations

import asyncio
import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from qa_common.targets import assert_target

from corpus.generate import generate_corpus

DOCUMENT_TYPES = [
    "invoice",
    "purchase_order",
    "bank_statement",
    "utility_bill",
    "letter",
]


def _read_labels(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_metrics(
    actual: list[str],
    predicted: list[str],
    classes: list[str],
) -> dict[str, Any]:
    """Compute precision, recall, F1, macro-F1, and confusion matrix in pure Python."""
    # Initialize confusion matrix
    matrix: dict[str, dict[str, int]] = {
        c_true: {c_pred: 0 for c_pred in [*classes, "none"]} for c_true in classes
    }

    for a, p in zip(actual, predicted):
        pred_key = p if p in classes else "none"
        if a in matrix:
            matrix[a][pred_key] += 1

    per_class: dict[str, dict[str, float]] = {}
    f1_scores: list[float] = []
    recalls: list[float] = []

    for c in classes:
        tp = matrix[c].get(c, 0)
        fp = sum(matrix[other_c].get(c, 0) for other_c in classes if other_c != c)
        fn = sum(matrix[c].get(pred_c, 0) for pred_c in [*classes, "none"] if pred_c != c)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class[c] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
        f1_scores.append(f1)
        recalls.append(recall)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    min_recall = min(recalls) if recalls else 0.0

    return {
        "per_class": per_class,
        "macro_f1": round(macro_f1, 4),
        "min_recall": round(min_recall, 4),
        "confusion_matrix": matrix,
    }


async def _poll_tasks_until_done(
    client: httpx.AsyncClient,
    tasks_url: str,
    headers: dict[str, str],
    target_task_ids: set[str],
    timeout_s: float = 600.0,
) -> dict[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    final_tasks: dict[str, dict[str, Any]] = {}
    last_print = time.time()

    while time.time() < deadline:
        resp = await client.get(tasks_url, headers=headers, timeout=15.0)
        assert resp.status_code == 200
        for t in resp.json():
            tid = t.get("task_id")
            if tid in target_task_ids and t.get("status") in ("SUCCESS", "FAILURE"):
                final_tasks[tid] = t

        if len(final_tasks) == len(target_task_ids):
            print(f" [Tasks Drained] {len(final_tasks)}/{len(target_task_ids)} in {timeout_s - (deadline - time.time()):.1f}s")
            return final_tasks

        if time.time() - last_print >= 15.0:
            print(f" [Polling] {len(final_tasks)}/{len(target_task_ids)} tasks drained...")
            last_print = time.time()

        await asyncio.sleep(2.0)

    raise TimeoutError(f"Tasks did not drain in {timeout_s}s. {len(final_tasks)}/{len(target_task_ids)}")


async def run_single_seed_eval(
    seed: int,
    base_url: str,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> dict[str, Any]:
    """Run full evaluation protocol for a single seed."""
    seed_dir = tmp_path / f"eval_seed_{seed}"
    labels_file = seed_dir / "labels.csv"
    manifest_file = seed_dir / "manifest.sha256"

    # Generate 600 corpus PDFs for this seed (600 ingest: 120 per document type)
    await asyncio.to_thread(
        generate_corpus,
        seed=seed,
        count=600,
        output_dir=seed_dir,
        labels_file=labels_file,
        manifest_file=manifest_file,
        corrupt_ratio=0.0,
        duplicate_ratio=0.0,
    )
    rows = await asyncio.to_thread(_read_labels, labels_file)

    # Filter to ingest-eligible documents
    valid_rows = [r for r in rows if r["expected_outcome"] == "ingest"]
    # Group by type for stratified split
    by_type: dict[str, list[dict[str, str]]] = {dt: [] for dt in DOCUMENT_TYPES}
    for r in valid_rows:
        by_type[r["type"]].append(r)

    # 100 per type for training (500 total), 20 per type for held-out test (100 total)
    train_rows: list[dict[str, str]] = []
    test_rows: list[dict[str, str]] = []
    for dt in DOCUMENT_TYPES:
        train_rows.extend(by_type[dt][:100])
        test_rows.extend(by_type[dt][100:120])

    assert len(train_rows) == 500
    assert len(test_rows) == 100

    # Clean previous documents and model file from database
    await asyncio.to_thread(
        subprocess.run,
        [
            "docker", "compose", "exec", "-T", "webserver", "python3", "manage.py", "shell", "-c",
            (
                "from django.conf import settings; settings.MODEL_FILE.unlink(missing_ok=True); "
                "from documents.models import Document, PaperlessTask; "
                "Document.global_objects.all().delete(); PaperlessTask.objects.all().delete()"
            ),
        ],
        check=True,
        capture_output=True,
    )

    upload_url = f"{base_url}/api/documents/post_document/"
    tasks_url = f"{base_url}/api/tasks/"
    doc_types_url = f"{base_url}/api/document_types/"

    async with httpx.AsyncClient() as client:
        # Step 1: Ensure 5 document types with matching_algorithm=6 (MATCH_AUTO)
        type_id_map: dict[str, int] = {}
        for dt_name in DOCUMENT_TYPES:
            # Check if exists or create
            dt_resp = await client.get(f"{doc_types_url}?name__iexact={dt_name}", headers=auth_headers)
            results = dt_resp.json().get("results", [])
            if results:
                type_id = results[0]["id"]
                # Update matching_algorithm if needed
                await client.patch(
                    f"{doc_types_url}{type_id}/",
                    headers=auth_headers,
                    json={"matching_algorithm": 6},
                )
            else:
                create_resp = await client.post(
                    doc_types_url,
                    headers=auth_headers,
                    json={"name": dt_name, "matching_algorithm": 6},
                )
                assert create_resp.status_code == 201
                type_id = create_resp.json()["id"]
            type_id_map[dt_name] = type_id

        # Step 2: Ingest 500 training files with document_type set
        semaphore = asyncio.Semaphore(40)
        train_task_ids: set[str] = set()

        async def _upload_train(row: dict[str, str]) -> None:
            filename = row["file"]
            filepath = seed_dir / filename
            dt_id = type_id_map[row["type"]]
            file_bytes = filepath.read_bytes()
            async with semaphore:
                resp = await client.post(
                    upload_url,
                    headers=auth_headers,
                    files={"document": (filename, file_bytes, "application/pdf")},
                    data={"document_type": dt_id},
                    timeout=60.0,
                )
                assert resp.status_code == 200
                train_task_ids.add(resp.json().strip())

        await asyncio.gather(*[_upload_train(r) for r in train_rows])
        await _poll_tasks_until_done(client, tasks_url, auth_headers, train_task_ids, timeout_s=900.0)

        # Step 3: Run pinned management command to train classifier
        train_cmd = [
            "docker", "compose", "exec", "-T", "webserver",
            "python3", "manage.py", "document_create_classifier",
        ]
        cmd_res = await asyncio.to_thread(subprocess.run, train_cmd, capture_output=True, text=True)
        assert cmd_res.returncode == 0, f"document_create_classifier failed: {cmd_res.stderr}"

        # Step 4: Ingest 100 held-out files WITHOUT labels
        test_task_ids: dict[str, str] = {}  # task_id -> true_type

        async def _upload_test(row: dict[str, str]) -> None:
            filename = row["file"]
            filepath = seed_dir / filename
            file_bytes = filepath.read_bytes()
            async with semaphore:
                resp = await client.post(
                    upload_url,
                    headers=auth_headers,
                    files={"document": (filename, file_bytes, "application/pdf")},
                    timeout=60.0,
                )
                assert resp.status_code == 200
                tid = resp.json().strip()
                test_task_ids[tid] = row["type"]

        await asyncio.gather(*[_upload_test(r) for r in test_rows])
        final_test_tasks = await _poll_tasks_until_done(
            client, tasks_url, auth_headers, set(test_task_ids.keys()), timeout_s=300.0
        )

        # Step 5: Gather predictions from created documents
        actual_labels: list[str] = []
        predicted_labels: list[str] = []
        id_to_type_name = {v: k for k, v in type_id_map.items()}

        for tid, true_type in test_task_ids.items():
            t_obj = final_test_tasks[tid]
            doc_id = t_obj.get("related_document")
            actual_labels.append(true_type)

            if doc_id:
                doc_resp = await client.get(f"{base_url}/api/documents/{doc_id}/", headers=auth_headers)
                assert doc_resp.status_code == 200
                assigned_type_id = doc_resp.json().get("document_type")
                pred_type = id_to_type_name.get(assigned_type_id, "none")
                predicted_labels.append(pred_type)
            else:
                predicted_labels.append("none")

    # Compute metrics in pure Python
    results = compute_metrics(actual_labels, predicted_labels, DOCUMENT_TYPES)
    return results


@pytest.mark.eval
@pytest.mark.req("REQ-ING-009")
@pytest.mark.asyncio
async def test_classifier_pre_registered_eval(
    base_url: str,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    """Run classifier evaluation across 3 seeds (42, 101, 202).

    Assert macro-F1 >= 0.90 and min recall >= 0.80.
    """
    seeds = [42, 101, 202]
    all_results: dict[int, dict[str, Any]] = {}

    macro_f1s: list[float] = []
    min_recalls: list[float] = []

    for seed in seeds:
        print(f"\n--- Running Classifier Eval for Seed {seed} ---")
        res = await run_single_seed_eval(seed, base_url, auth_headers, tmp_path)
        all_results[seed] = res
        macro_f1s.append(res["macro_f1"])
        min_recalls.append(res["min_recall"])
        print(f"Seed {seed} Macro-F1: {res['macro_f1']:.4f}, Min Recall: {res['min_recall']:.4f}")

    mean_macro_f1 = round(sum(macro_f1s) / len(macro_f1s), 4)
    min_macro_f1 = round(min(macro_f1s), 4)
    mean_min_recall = round(sum(min_recalls) / len(min_recalls), 4)
    abs_min_recall = round(min(min_recalls), 4)

    summary = {
        "seeds": seeds,
        "runs": {str(s): all_results[s] for s in seeds},
        "mean_macro_f1": mean_macro_f1,
        "min_macro_f1": min_macro_f1,
        "mean_min_recall": mean_min_recall,
        "abs_min_recall": abs_min_recall,
    }

    # Save to results/evals.json
    results_file = Path(__file__).resolve().parent.parent.parent / "results" / "evals.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"\n[EVAL RESULTS] Mean Macro-F1: {mean_macro_f1:.4f} (Target >= 0.90), "
        f"Abs Min Recall: {abs_min_recall:.4f} (Target >= 0.80)"
    )

    assert_target("classifier_macro_f1_rate", mean_macro_f1)
    assert_target("classifier_min_recall_rate", abs_min_recall)
