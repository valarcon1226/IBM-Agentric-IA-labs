# Execution Plan — Project 12: CI/CD & Automated Testing Pipeline

Source of truth: `README.md`.

## Prerequisites
- Docker engine and docker compose installed and running.
- Python 3.12 / 3.11 with `uv` virtual environment.
- GitHub repository with Actions enabled.
- Remote VPS target for deployment (when `DEPLOY_ENABLED="true"`).

---

## Build Checklist

- [x] Create application package `app/`:
  - `app/config.py`: Pydantic settings loading `.env` configuration.
  - `app/models.py`: SQLAlchemy `DeploymentModel` and Pydantic schemas (`DeploymentCreate`, `DeploymentUpdate`, `DeploymentResponse`, `HealthResponse`).
  - `app/database.py`: SQLAlchemy engine, session maker, `init_db` and `check_db_health`.
  - `app/crud.py`: CRUD operations for deployments.
  - `app/main.py`: FastAPI endpoints (`/health`, `/api/v1/deployments`).
- [x] Create test suite `tests/`:
  - `tests/conftest.py`: In-memory SQLite fixtures and FastAPI `TestClient`.
  - `tests/test_unit.py`: 14 unit tests covering CRUD, validations, filtering, errors, and database utilities.
  - `tests/test_integration.py`: Integration test connecting to a real `postgres:16-alpine` container via Testcontainers.
- [x] Configure code quality and typing tools:
  - `pyproject.toml`: Ruff linting (E, F, I, B, UP), Mypy, Pytest configuration with markers, coverage threshold (>= 80%).
  - `requirements.txt`: Pinned production dependencies (FastAPI, SQLAlchemy, psycopg2-binary, Uvicorn, Pydantic).
  - `requirements-dev.txt`: Pinned development dependencies (Ruff, Mypy, Bandit, Pytest, Pytest-cov, Testcontainers).
- [x] Multi-stage Docker containerization:
  - `Dockerfile`: Multi-stage build (`python:3.12-slim-bookworm`), non-root user `appuser` (UID 10001, GID 10001), system updates to mitigate CRITICAL CVEs.
  - `.dockerignore`: Ignore `.venv`, `__pycache__`, test artifacts.
- [x] Docker Compose stack:
  - `docker-compose.yml`: Services `db` (`postgres:16-alpine`) and `api` (`127.0.0.1:8022:8000`), with discrete healthchecks and isolated network.
  - `.env.example`: Configuration template with `change_me_` defaults.
- [x] GitHub Actions workflow `.github/workflows/12-ci-cd.yml`:
  - Path filters: `Portfolio-Automation/12-ci-cd-pipeline/**` and `.github/workflows/12-ci-cd.yml`.
  - Matrix testing: Python 3.11 and 3.12.
  - Quality gates: Ruff check, Ruff format check, Mypy type-check, Bandit SAST scan.
  - Tests: Pytest unit tests with coverage enforcement (>= 80%) + Testcontainers integration tests.
  - Container build & Trivy vulnerability scan failing on CRITICAL (`ignore-unfixed: true`).
  - GHCR publish on push to `main` and `portfolio-automation` with minimal permissions (`contents: read`, `packages: write`).
  - Guarded SSH deploy and manual rollback (`workflow_dispatch`) requiring `vars.DEPLOY_ENABLED == 'true'`.
  - All actions pinned by version tag.
- [x] Validation and Verification:
  - Ruff check & format check pass with 0 errors.
  - Mypy check passes with 0 errors.
  - Bandit scan passes with 0 issues.
  - Pytest unit tests pass (14 passed, >= 95% coverage).
  - Pytest integration tests with Testcontainers pass against real PostgreSQL.
  - Trivy scan passes with 0 CRITICAL vulnerabilities.
  - `actionlint` passes with 0 errors on `.github/workflows/12-ci-cd.yml`.
  - Docker Compose up/ps/e2e/down verified successfully.

---

## Definition of Done
- [x] CI/CD pipeline workflow created at repository root (`.github/workflows/12-ci-cd.yml`).
- [x] Existing workflow `.github/workflows/portfolio-automation-ci.yml` kept completely untouched.
- [x] Quality gates (Ruff, Mypy, Bandit, Pytest >= 80%, Trivy, Actionlint) passing locally and in CI.
- [x] Container runs as non-root user on slim image without CRITICAL vulnerabilities.
- [x] Deployment and rollback jobs present and disabled unless `vars.DEPLOY_ENABLED == 'true'`.
- [x] Documentation in `README.md` and `EXECUTION_PLAN.md` fully synchronized with actual code.
