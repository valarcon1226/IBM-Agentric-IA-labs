# Execution Plan — CI/CD & Automated Testing Pipeline

Source of truth: `README.md`. Can be applied to any single service repo in this portfolio — can start right after `01-smart-data-intake` is working, or be layered onto each project incrementally (see `docs/BUILD-PLAN.md` at the portfolio root).

## Prerequisites
- A GitHub repository with Actions enabled
- Target service already has a working Dockerfile-buildable app and a `tests/` directory
- SSH access to a deploy target (VPS) for the CD steps

## Build Checklist

- [ ] Add `.github/workflows/ci.yml` (README section 5).
  - Verify: valid YAML; no syntax errors on push.
- [ ] Add `.github/workflows/cd.yml` (README section 5).
  - Verify: valid YAML; only references named secrets, no hardcoded credentials.
- [ ] Add repo secrets: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`, `SLACK_WEBHOOK`, `CR_PAT`.
  - `CR_PAT`: a fine-grained personal access token with **only** `read:packages`, used by the VPS to pull from GHCR (`cd.yml` pipes it to `docker login --password-stdin`). Never commit it.
  - Verify: all 5 present under Settings → Secrets and variables → Actions.
  - Verify (on the VPS): `echo "$CR_PAT" | docker login ghcr.io -u <github-user> --password-stdin` → `Login Succeeded`.
- [ ] Enable GHCR write permissions for Actions.
  - Verify: a manual push test to `ghcr.io/<repo>` succeeds (no 403).
- [ ] Add the multi-stage Dockerfile (README section 4) to the target service.
  - Verify: `docker build` succeeds; container runs as non-root `appuser`.
- [ ] Raise test coverage to ≥80% (`pytest --cov=src --cov-fail-under=80`).
  - Verify: coverage gate passes locally.
- [ ] Open a dry-run PR to trigger `ci.yml`.
  - Verify: Ruff, Mypy, Bandit, Pytest all green on the PR.
- [ ] Merge to `main` to trigger `cd.yml`.
  - Verify: GHCR push succeeds, SSH deploy succeeds, post-deploy health check passes.
- [ ] Manually trigger `rollback.yml` with an older SHA.
  - Verify: the deployed service's version/health endpoint reflects the rolled-back SHA.

## Definition of Done
- [ ] Every PR against `main` runs lint + type-check + security scan + tests automatically.
- [ ] Merging to `main` deploys automatically with zero manual SSH steps.
- [ ] Rollback to a previous SHA verified to work at least once.
- [ ] Coverage gate enforced at ≥80%.
