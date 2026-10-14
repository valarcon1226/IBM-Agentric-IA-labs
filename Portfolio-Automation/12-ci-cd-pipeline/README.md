# Project 12: CI/CD & Automated Testing Pipeline

## 1. Problem Statement
Manual testing and deployments introduce high risk, human error, and downtime. This project implements a secure, automated Continuous Integration and Continuous Deployment (CI/CD) pipeline using GitHub Actions, containerization, and static/dynamic security analysis.

It guarantees that code is linted, type-checked, security-scanned (SAST), tested against isolated unit and integration environments with Testcontainers, packaged in a multi-stage non-root container, scanned for container CVEs (Trivy), published to GitHub Container Registry (GHCR), and deployed safely via SSH with rollback capabilities.

---

## 2. Architecture & Pipeline Stages

```mermaid
flowchart TD
    Dev((Developer)) -->|Push / PR| GH[GitHub Repository]

    subgraph CI ["CI Pipeline (Matrix: Python 3.11, 3.12)"]
        GH --> Lint["Ruff Check & Format"]
        Lint --> Type["Mypy Type-check"]
        Type --> SAST["Bandit Security Scan"]
        SAST --> Unit["Pytest (Coverage >= 80%)"]
        Unit --> Int["Testcontainers (PostgreSQL 16)"]
    end

    subgraph Security ["Container Build & Security Scan"]
        Int --> DockerBuild["Multi-Stage Docker Build (Slim, Non-Root)"]
        DockerBuild --> Trivy["Trivy Vulnerability Scan (Fails on CRITICAL)"]
    end

    subgraph CD ["CD & Deployment (main / portfolio-automation)"]
        Trivy --> Publish["Publish to GHCR (ghcr.io)"]
        Publish --> DeployCheck{"vars.DEPLOY_ENABLED == 'true'?"}
        DeployCheck -->|Yes| SSHDeploy["SSH Deploy to VPS (Zero Downtime)"]
        DeployCheck -->|No| Disabled["Deploy Skipped (Guarded)"]
    end

    subgraph Ops ["Rollback Operations (Manual)"]
        Dispatch["workflow_dispatch (image_tag)"] --> RollbackCheck{"vars.DEPLOY_ENABLED == 'true'?"}
        RollbackCheck -->|Yes| SSHRollback["SSH Rollback & Verification"]
        RollbackCheck -->|No| RollbackDisabled["Rollback Skipped (Guarded)"]
    end
```

---

## 3. Tech Stack
*   **CI/CD Engine:** GitHub Actions (`.github/workflows/12-ci-cd.yml`)
*   **Workflow Linter:** `actionlint` (rhysd/actionlint)
*   **Application:** FastAPI (Python 3.12 / 3.11) with SQLAlchemy 2.0 ORM
*   **Database:** PostgreSQL 16 (`postgres:16-alpine`)
*   **Linting & Formatting:** Ruff
*   **Type Checking:** Mypy
*   **Security Analysis:** Bandit (SAST AST scanner), Trivy (Container CVE scanner)
*   **Testing:** Pytest, pytest-cov, Testcontainers (`testcontainers[postgres]`)
*   **Containerization:** Docker multi-stage build, non-root user (`appuser`, UID 10001), `python:3.12-slim-bookworm`
*   **Registry:** GitHub Container Registry (`ghcr.io`)
*   **Deployment:** Docker Compose, SSH (`appleboy/ssh-action`)

---

## 4. File Structure
```
Portfolio-Automation/
├── .github/
│   └── workflows/
│       ├── 12-ci-cd.yml                     # Unified CI/CD workflow (root)
│       └── portfolio-automation-ci.yml      # Portfolio-wide CI (untouched)
└── 12-ci-cd-pipeline/
    ├── app/
    │   ├── __init__.py
    │   ├── config.py                        # Pydantic Settings
    │   ├── crud.py                          # SQLAlchemy CRUD operations
    │   ├── database.py                      # Engine, sessionmaker, health checks
    │   ├── main.py                          # FastAPI endpoints (/health, /api/v1/deployments)
    │   └── models.py                        # SQLAlchemy & Pydantic schemas
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py                      # SQLite in-memory fixtures & TestClient
    │   ├── test_integration.py              # Real PostgreSQL testcontainers suite
    │   └── test_unit.py                     # Comprehensive unit & endpoint tests
    ├── .dockerignore
    ├── .env.example
    ├── .gitignore
    ├── docker-compose.yml                   # Services: db (Postgres), api (127.0.0.1:8022:8000)
    ├── Dockerfile                           # Multi-stage, slim, non-root runner
    ├── EXECUTION_PLAN.md                    # Synchronized execution checklist
    ├── pyproject.toml                       # Ruff, mypy, pytest, coverage config
    ├── README.md                            # Complete technical documentation
    ├── requirements.txt                     # Pinned runtime dependencies
    └── requirements-dev.txt                 # Pinned development & testing dependencies
```

---

## 5. API Endpoints
The sample service manages deployment records in PostgreSQL:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check verifying API and PostgreSQL connectivity |
| `POST` | `/api/v1/deployments` | Create a new deployment record (Status 201) |
| `GET` | `/api/v1/deployments` | List deployments (filters: `environment`, `status`, pagination: `skip`, `limit`) |
| `GET` | `/api/v1/deployments/{id}` | Retrieve deployment by ID (Status 200 or 404) |
| `PUT` | `/api/v1/deployments/{id}` | Update deployment fields (Status 200 or 404) |
| `DELETE` | `/api/v1/deployments/{id}` | Delete deployment (Status 204 or 404) |

---

## 6. Security & Hardening

1. **Non-Root Container Execution:**
   The multi-stage `Dockerfile` creates a dedicated group `appgroup` (GID 10001) and user `appuser` (UID 10001). The container runs without root privileges.
2. **SAST Analysis (Bandit):**
   Bandit scans all Python code in `app/` to detect security anti-patterns, hardcoded credentials, and unsafe calls.
3. **Container CVE Scanning (Trivy):**
   Trivy scans the generated Docker image and fails the build on any `CRITICAL` vulnerability (`--severity CRITICAL --exit-code 1 --ignore-unfixed`). System packages are patched during image build.
4. **Least-Privilege GitHub Actions:**
   - Top-level permissions default to `contents: read`.
   - The `publish` job explicitly requests only `packages: write`.
   - All actions are pinned to specific version tags (`@v4.2.2`, `@v5.3.0`, `@v3.8.0`, `@v3.3.0`, `@v6.11.0`, `@v4.5.0`, `@v1.2.0`, `0.28.0`).
5. **Path Filtering:**
   The workflow triggers only on modifications to `Portfolio-Automation/12-ci-cd-pipeline/**` and `.github/workflows/12-ci-cd.yml`, avoiding unnecessary CI runs when other projects change.

---

## 7. Secrets and Environment Variables

### Required Repository Secrets
Configure these in GitHub under **Settings > Secrets and variables > Actions > Secrets**:

| Secret Name | Description | Example |
|---|---|---|
| `SERVER_HOST` | VPS IP address or domain for SSH deployment | `192.168.1.50` |
| `SERVER_USER` | Non-root SSH deployment user on target host | `deploy` |
| `SERVER_SSH_KEY` | Private SSH key (ED25519 or RSA) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `CR_PAT` | Fine-grained Personal Access Token with `read:packages` used by host to pull from GHCR | `ghp_...` |

*(Note: `GITHUB_TOKEN` is automatically supplied by GitHub Actions with minimal scoped permissions).*

### Repository Variables (Deployment Gate)
Configure under **Settings > Secrets and variables > Actions > Variables**:

| Variable Name | Required Value | Default | Description |
|---|---|---|---|
| `DEPLOY_ENABLED` | `"true"` | (empty/disabled) | Controls SSH deployment and manual rollback jobs. If unset or not `"true"`, deployment and rollback jobs are skipped safely. |

---

## 8. Branch Protection Rules

To safeguard `main` and `portfolio-automation`, configure branch protection under **Settings > Branches > Branch protection rules**:

1. **Require a pull request before merging:**
   - Require approvals: 1
   - Dismiss stale pull request approvals when new commits are pushed: Enabled.
2. **Require status checks to pass before merging:**
   - `Test (Python 3.11)`
   - `Test (Python 3.12)`
   - `Build image and scan with Trivy`
3. **Do not allow bypassing the above settings:** Enabled for all users and administrators.

---

## 9. Rollback Procedure

When an emergency rollback is required:
1. Navigate to **Actions > 12-ci-cd > Run workflow**.
2. Provide the input `image_tag` with the target Git commit SHA or specific image tag to restore (e.g. `a1b2c3d4e5f6`).
3. If `vars.DEPLOY_ENABLED` is `"true"`, the `rollback` job will:
   - Log in to GHCR on the host.
   - Pull the specified image tag.
   - Retag it as `latest`.
   - Restart the container with `docker compose up -d --no-deps api`.
   - Run a live health check against `http://127.0.0.1:8022/health` to confirm recovery.

---

## 10. Local Verification Guide

Run the complete quality gate from the repository:

```powershell
# 1. Activate virtual environment
cd 12-ci-cd-pipeline
.\.venv\Scripts\activate

# 2. Linting & Formatting Check
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests

# 3. Type Checking
.\.venv\Scripts\mypy.exe app

# 4. SAST Security Scan
.\.venv\Scripts\bandit.exe -r app

# 5. Unit Tests with Coverage (>= 80%)
.\.venv\Scripts\pytest.exe -q --cov=app --cov-report=term --cov-fail-under=80

# 6. Integration Tests with Testcontainers (real PostgreSQL)
.\.venv\Scripts\pytest.exe -m integration -q

# 7. Multi-stage Docker Image Build
docker build -t 12-ci-cd-pipeline:test .

# 8. Trivy Security Scan (Fails on CRITICAL)
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity CRITICAL --exit-code 1 --ignore-unfixed 12-ci-cd-pipeline:test

# 9. GitHub Actions Workflow Linting
docker run --rm -v "${PWD}/..:/repo" -w /repo rhysd/actionlint .github/workflows/12-ci-cd.yml

# 10. Full Docker Compose Stack Test
docker compose up -d --build
docker compose ps
# Verify health endpoint
curl -sf http://127.0.0.1:8022/health
# Tear down with volumes
docker compose down -v
```
