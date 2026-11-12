"""MinIO object storage integration for invoices and raw OCR text sidecars."""

import io
import logging

from minio import Minio

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages file storage in MinIO."""

    def __init__(self) -> None:
        self.endpoint = settings.minio_endpoint
        self.bucket = settings.minio_bucket
        self.client = Minio(
            self.endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        """Creates the bucket if it does not already exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("MinIO bucket '%s' created.", self.bucket)
        except Exception as exc:
            logger.warning("Could not ensure MinIO bucket '%s': %s", self.bucket, exc)

    def upload_file(
        self, object_key: str, data: bytes, content_type: str = "application/pdf"
    ) -> str:
        """Uploads binary data to MinIO and returns the object key."""
        self.ensure_bucket()
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        return object_key

    def upload_text(self, object_key: str, text: str) -> str:
        """Uploads raw text sidecar to MinIO."""
        return self.upload_file(
            object_key, text.encode("utf-8"), content_type="text/plain; charset=utf-8"
        )

    def get_file(self, object_key: str) -> bytes:
        """Downloads object data from MinIO."""
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


storage_service = StorageService()
