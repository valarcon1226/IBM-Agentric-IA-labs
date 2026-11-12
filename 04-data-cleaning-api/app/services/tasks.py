import io
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pandas as pd

from app.core.worker import celery_app
from app.models.db import JobStatus

from . import jobs_repo
from .cleaner import clean_dataframe
from .enricher import normalize_phones, validate_emails
from .readers import read_table
from .storage import download_file, upload_file
from .transformer import aggregate_data, melt_data, merge_columns, pivot_data, split_column

logger = logging.getLogger(__name__)

RESULTS_PREFIX = "results"
TRANSFORMS: dict[str, Callable[..., pd.DataFrame]] = {
    "pivot": pivot_data,
    "melt": melt_data,
    "merge": merge_columns,
    "split": split_column,
    "aggregate": aggregate_data,
}


def _load(file_path: str) -> pd.DataFrame:
    return read_table(download_file(file_path), file_path)


def _run(job_id: str, output_name: str, build: Callable[[], pd.DataFrame]) -> None:
    """Run one job: mark PROCESSING, build the result, store it, mark COMPLETED or FAILED."""
    jid = UUID(job_id)
    jobs_repo.set_status(jid, JobStatus.PROCESSING)
    try:
        out = io.BytesIO()
        build().to_csv(out, index=False)
        key = upload_file(out.getvalue(), f"{RESULTS_PREFIX}/{output_name}")
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        jobs_repo.set_status(jid, JobStatus.FAILED, error_message=f"{type(e).__name__}: {e}")
        return
    jobs_repo.set_status(jid, JobStatus.COMPLETED, output_file_path=key)


def _transform(file_path: str, params: dict[str, Any]) -> pd.DataFrame:
    t_type = params.get("type")
    if t_type not in TRANSFORMS:
        raise ValueError(f"Unknown transform: {t_type}")
    return TRANSFORMS[t_type](_load(file_path), **params.get("args", {}))


def _enrich(file_path: str, ops: list[str], cols: dict[str, str]) -> pd.DataFrame:
    df = _load(file_path)
    if "validate_emails" in ops and cols.get("email"):
        df = validate_emails(df, cols["email"])
    if "normalize_phones" in ops and cols.get("phone"):
        df = normalize_phones(df, cols["phone"])
    return df


@celery_app.task
def process_clean_job(job_id: str, file_path: str, options: dict[str, Any]) -> None:
    _run(job_id, f"cleaned_{job_id}.csv", lambda: clean_dataframe(_load(file_path), options))


@celery_app.task
def process_transform_job(job_id: str, file_path: str, params: dict[str, Any]) -> None:
    _run(job_id, f"transformed_{job_id}.csv", lambda: _transform(file_path, params))


@celery_app.task
def process_enrich_job(job_id: str, file_path: str, ops: list[str], cols: dict[str, str]) -> None:
    _run(job_id, f"enriched_{job_id}.csv", lambda: _enrich(file_path, ops, cols))
