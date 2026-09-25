import io
import logging
from collections.abc import Callable

import pandas as pd

from app.core.worker import celery_app

from .cleaner import clean_dataframe
from .enricher import normalize_phones, validate_emails
from .storage import download_file, upload_file
from .transformer import aggregate_data, melt_data, merge_columns, pivot_data, split_column

logger = logging.getLogger(__name__)


def update_job_status(job_id, status, error_message=None):
    pass


@celery_app.task
def process_clean_job(job_id: str, file_path: str, options: dict):
    update_job_status(job_id, "PROCESSING")
    try:
        df = pd.read_csv(io.BytesIO(download_file(file_path)))
        cleaned_df = clean_dataframe(df, options)
        out = io.BytesIO()
        cleaned_df.to_csv(out, index=False)
        upload_file(out.getvalue(), f"cleaned_{job_id}.csv")
        update_job_status(job_id, "COMPLETED")
    except Exception as e:
        update_job_status(job_id, "FAILED", str(e))


@celery_app.task
def process_transform_job(job_id: str, file_path: str, params: dict):
    update_job_status(job_id, "PROCESSING")
    try:
        df = pd.read_csv(io.BytesIO(download_file(file_path)))
        t_type = params.get("type")
        args = params.get("args", {})

        funcs: dict[str, Callable[..., pd.DataFrame]] = {
            "pivot": pivot_data,
            "melt": melt_data,
            "merge": merge_columns,
            "split": split_column,
            "aggregate": aggregate_data,
        }
        if t_type in funcs:
            res_df = funcs[t_type](df, **args)
        else:
            raise ValueError("Unknown transform")

        out = io.BytesIO()
        res_df.to_csv(out, index=False)
        upload_file(out.getvalue(), f"transformed_{job_id}.csv")
        update_job_status(job_id, "COMPLETED")
    except Exception as e:
        update_job_status(job_id, "FAILED", str(e))


@celery_app.task
def process_enrich_job(job_id: str, file_path: str, ops: list, cols: dict):
    update_job_status(job_id, "PROCESSING")
    try:
        df = pd.read_csv(io.BytesIO(download_file(file_path)))
        if "validate_emails" in ops and cols.get("email"):
            df = validate_emails(df, cols["email"])
        if "normalize_phones" in ops and cols.get("phone"):
            df = normalize_phones(df, cols["phone"])
        out = io.BytesIO()
        df.to_csv(out, index=False)
        upload_file(out.getvalue(), f"enriched_{job_id}.csv")
        update_job_status(job_id, "COMPLETED")
    except Exception as e:
        update_job_status(job_id, "FAILED", str(e))
