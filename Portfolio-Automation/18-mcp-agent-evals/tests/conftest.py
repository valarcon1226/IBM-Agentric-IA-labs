"""Pytest configuration, CLI options, and shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import init_db


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options."""
    parser.addoption(
        "--model",
        action="store",
        default="fake",
        help="Model to use for evals tests ('fake' by default, or an Ollama/OpenAI model name)",
    )


@pytest.fixture
def model_name(pytestconfig: pytest.Config) -> str:
    """Return the model name requested via CLI."""
    return pytestconfig.getoption("--model")


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ensure each test runs with an isolated, clean SQLite database."""
    test_db_path = tmp_path / "test_restaurant.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db_path))
    monkeypatch.setenv("RESERVAS_FECHA_REFERENCIA", "2026-10-14")
    init_db(test_db_path)
    return test_db_path
