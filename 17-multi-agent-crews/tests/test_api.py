import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Report

client = TestClient(main.app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("engine", ["crewai", "autogen"])
def test_create_and_read_report(engine):
    created = client.post("/reports", json={"topic": "demanda de agentes de IA", "engine": engine})
    assert created.status_code == 202 and created.json()["status"] == "pending"
    # TestClient runs background tasks before returning, so the report is ready here.
    got = client.get(f"/reports/{created.json()['id']}").json()
    assert got["status"] == "completed", got["error"]
    assert Report(**got["report"]).sources


@pytest.mark.parametrize(
    "body", [{"topic": "", "engine": "crewai"}, {"topic": "ok topic", "engine": "langgraph"}, {"engine": "crewai"}]
)
def test_invalid_requests(body):
    assert client.post("/reports", json=body).status_code == 422


def test_unknown_report():
    assert client.get("/reports/999").status_code == 404


def test_engine_failure_is_reported(monkeypatch):
    def boom(topic):
        raise RuntimeError("LLM down")

    monkeypatch.setitem(main.ENGINES, "crewai", boom)
    rid = client.post("/reports", json={"topic": "algo", "engine": "crewai"}).json()["id"]
    got = client.get(f"/reports/{rid}").json()
    assert got["status"] == "failed" and "LLM down" in got["error"]
