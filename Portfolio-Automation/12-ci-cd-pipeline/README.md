# Project: CI/CD & Automated Testing Pipeline

## 1. Problem Statement
Manual testing and deployments introduce high risk, human error, and downtime. This project implements an automated, zero-touch Continuous Integration and Continuous Deployment (CI/CD) pipeline using GitHub Actions. It guarantees that code is linted, type-checked, security-scanned, tested, and safely deployed to production with zero downtime.

## 2. Architecture
```mermaid
flowchart TD
    Developer((Developer)) -->|Push/PR| GitHub[GitHub Repository]
    
    subgraph CI Pipeline [GitHub Actions: ci.yml]
        GitHub --> Lint[Ruff & Mypy]
        Lint --> SecScan[Bandit & Trivy]
        SecScan --> Test[Pytest & Coverage & Testcontainers]
    end
    
    subgraph CD Pipeline [GitHub Actions: cd.yml]
        Test --> Build[Docker Multi-Stage Build]
        Build --> Push[Push to GHCR]
        Push --> Deploy[SSH Deploy to VPS]
        Deploy --> Verify[Health Check & Verification]
        Verify --> Notify[Slack/Email Notification]
    end
```

## 3. Tech Stack
*   **CI/CD Engine:** GitHub Actions
*   **Registry:** GitHub Container Registry (ghcr.io)
*   **Testing:** Pytest, pytest-cov, Testcontainers (testcontainers-python)
*   **Linting & Type Checking:** Ruff, Mypy
*   **Security:** Bandit (SAST), Trivy (Container Vulnerabilities)
*   **Deployment:** SSH, Docker Compose (Zero-downtime methodology)

## 4. File Structure
```
.
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── cd.yml
│       ├── rollback.yml
│       └── scheduled-tests.yml
├── src/
│   └── main.py
├── tests/
│   └── test_main.py
├── Dockerfile
├── requirements.txt
├── pytest.ini
└── README.md
```

## 5. Multi-Stage Dockerfile (Example: FastAPI)
```dockerfile
# Stage 1: Builder
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --target=/app/deps

# Stage 2: Production
FROM python:3.12-slim as production
WORKDIR /app
COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages
COPY ./src /app/src
RUN useradd -m appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 6. GitHub Actions Workflows

### `.github/workflows/ci.yml` (Pull Requests)
```yaml
name: CI Pipeline

on:
  pull_request:
    branches: [ main ]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy pytest pytest-cov bandit testcontainers
          pip install -r requirements.txt
          
      - name: Lint with Ruff
        run: ruff check .
        
      - name: Type check with mypy
        run: mypy src/
        
      - name: Security Scan (Bandit)
        run: bandit -r src/
        
      - name: Run Tests
        run: pytest --cov=src --cov-fail-under=80 tests/
        
      - name: Upload Coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report-${{ matrix.python-version }}
          path: coverage.xml
```

### `.github/workflows/cd.yml` (Deploy to Production)
```yaml
name: CD Pipeline

on:
  push:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/fastapi-gateway

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      
    steps:
      - uses: actions/checkout@v4
      
      - name: Log in to the Container registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }},${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
          
      - name: Deploy to VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/portfolio
            echo "${{ secrets.CR_PAT }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            docker compose pull fastapi-gateway
            docker compose up -d --no-deps fastapi-gateway
            
            # VPS-side Health Check
            echo "Waiting for service to start..."
            sleep 15
            if ! curl -sf http://localhost:8000/health; then
              echo "Health check failed! Service is not healthy."
              exit 1
            fi
            echo "Deployment healthy!"
          
      - name: Notify Slack
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          fields: repo,message,commit,author,action,eventName,ref,workflow,job,took
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

### `.github/workflows/rollback.yml` (Manual Rollback)
```yaml
name: Rollback Pipeline

on:
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'The full Git SHA tag to rollback to'
        required: true
        type: string

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/fastapi-gateway

jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - name: Rollback on VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/portfolio
            # Update docker-compose or pull specific image
            docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.event.inputs.image_tag }}
            
            # Typically you'd tag it as latest to simplify docker-compose or update the tag in env
            docker tag ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.event.inputs.image_tag }} ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            
            docker compose up -d --no-deps fastapi-gateway
            
            sleep 15
            if ! curl -sf http://localhost:8000/health; then
              echo "Health check failed after rollback."
              exit 1
            fi
            echo "Rollback successful!"
```

## 7. Secrets Management

| Secret Name | Description | Example |
|---|---|---|
| `SERVER_HOST` | VPS IP address or domain | `192.168.1.50` |
| `SERVER_USER` | SSH user for deployment | `deploy` |
| `SERVER_SSH_KEY` | Private SSH key (ED25519) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `SLACK_WEBHOOK` | Webhook URL for Slack alerts | `https://hooks.slack.com/services/...` |
| `CR_PAT` | Personal Access Token for GHCR | `ghp_...` |

Configure these in your GitHub Repository under **Settings > Secrets and variables > Actions**.

## 8. Integration Testing with Testcontainers
For integration tests that require databases, we use `testcontainers-python` to spin up ephemeral containers during CI.

Example in `tests/test_db.py`:
```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def postgres_db():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()

def test_database_connection(postgres_db):
    assert "postgresql://" in postgres_db
    # Pass this URL to your app configuration for testing
```

## 9. Branch Protection & Policies
To ensure code quality, configure branch protection rules on `main`:
1. **Require pull request reviews before merging.**
2. **Require status checks to pass before merging:**
   *   `lint-and-test (3.11)`
   *   `lint-and-test (3.12)`
3. **Do not allow bypassing the above settings.**

## 10. Implementation Steps
1.  **Write `ci.yml`:** add the workflow from section 6 to `.github/workflows/ci.yml`. *Verify:* the file is valid YAML.
2.  **Write `cd.yml`:** add the workflow from section 6 to `.github/workflows/cd.yml`.
3.  **Write `rollback.yml`:** add the workflow from section 6 to `.github/workflows/rollback.yml`.
4.  **Configure repository secrets:** add `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`, `SLACK_WEBHOOK` in GitHub Settings.
5.  **Configure GHCR permissions:** enable "Read and write permissions" for GitHub Actions.
6.  **Write the multi-stage Dockerfile:** add the Dockerfile from section 5. *Verify:* `docker build -t test-image .` succeeds.
7.  **Reach 80% coverage:** add tests to hit `pytest --cov-fail-under=80`.
8.  **Pipeline dry run:** open a PR to trigger `ci.yml`.
9.  **Merge & deploy:** merge to `main` to trigger `cd.yml` and check the health check output on the VPS.
10. **Verify rollback:** trigger `rollback.yml` manually using a past Git SHA.
