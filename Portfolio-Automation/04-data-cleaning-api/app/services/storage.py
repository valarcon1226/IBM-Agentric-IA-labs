import io
import logging
from datetime import timedelta

from minio import Minio

from app.core.config import settings

logger = logging.getLogger(__name__)

client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)
BUCKET_NAME = settings.MINIO_BUCKET


def _ensure_bucket():
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)


def upload_file(file_content: bytes, filename: str) -> str:
    _ensure_bucket()
    client.put_object(BUCKET_NAME, filename, io.BytesIO(file_content), len(file_content))
    return filename


def download_file(object_key: str) -> bytes:
    response = client.get_object(BUCKET_NAME, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def generate_presigned_url(object_key: str, expires: int = 3600) -> str:
    return client.presigned_get_object(BUCKET_NAME, object_key, expires=timedelta(seconds=expires))
