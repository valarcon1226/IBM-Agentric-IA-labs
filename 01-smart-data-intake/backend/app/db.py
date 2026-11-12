from functools import cache

from minio import Minio
from redis import Redis
from sqlalchemy import create_engine, text

from app.config import settings


@cache
def get_engine():
    return create_engine(settings.DATABASE_URL)


@cache
def get_redis():
    return Redis.from_url(settings.REDIS_URL)


@cache
def get_minio():
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )


def check_dependencies() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    get_redis().ping()
    get_minio().list_buckets()
