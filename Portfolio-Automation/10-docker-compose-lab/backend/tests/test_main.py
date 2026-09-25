import pytest
from fastapi.testclient import TestClient

from src import main
from src.config import Settings, require_api_settings

client = TestClient(main.app)


def _deps(monkeypatch, *, redis_ok: bool, db_ok: bool) -> None:
    async def fake_redis(url):
        return redis_ok

    async def fake_db():
        return db_ok

    monkeypatch.setattr(main, "check_redis_connection", fake_redis)
    monkeypatch.setattr(main, "check_db_connection", fake_db)


def test_health_ok_when_dependencies_up(monkeypatch):
    _deps(monkeypatch, redis_ok=True, db_ok=True)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_health_503_when_redis_down(monkeypatch):
    _deps(monkeypatch, redis_ok=False, db_ok=True)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["services"]["redis"] == "down"


def test_health_503_when_database_down(monkeypatch):
    _deps(monkeypatch, redis_ok=True, db_ok=False)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["services"]["database"] == "down"


def test_jwt_secret_is_read_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_text("s3cret\n", encoding="utf-8")

    s = Settings(_env_file=None, JWT_SECRET_FILE=str(secret_file))  # type: ignore[call-arg]

    assert s.JWT_SECRET == "s3cret"


def test_api_refuses_to_start_without_secret_or_database(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL, JWT_SECRET"):
        require_api_settings(Settings(_env_file=None))  # type: ignore[call-arg]
