# 39 · Selenium 4 to Playwright Migration & Benchmark over OWASP Juice Shop

[![CI - Selenium to Playwright Benchmark](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/39-selenium-to-playwright-migration.yml/badge.svg)](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/39-selenium-to-playwright-migration.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/selenium-v4.52.0-green.svg)](https://www.selenium.dev/)
[![Playwright](https://img.shields.io/badge/playwright-v1.65.0-orange.svg)](https://playwright.dev/python/)
[![Browser](https://img.shields.io/badge/browser-Microsoft%20Edge-blue.svg)](https://www.microsoft.com/edge)

An objective, measured migration case study: the **identical 8 end-to-end user journeys** implemented twice in Python—first using **Selenium 4** (with explicit `WebDriverWait` and Page Objects) and then using **Playwright** (with `pytest-playwright` and unified locators)—tested repeatedly against local containerized **OWASP Juice Shop** (`v17.1.1`) to measure execution velocity, intermittent failure rates, and code economy.

---

## 1. What Exists Today

- **System Under Test (SUT)**: Containerized OWASP Juice Shop (`v17.1.1`) running on `127.0.0.1:3000` with automated healthcheck validation.
- **Fair & Strict Comparison**:
  - Both suites exercise the exact same 8 test scenarios with identical test names.
  - Zero arbitrary sleeps (`time.sleep`) across both suites; Selenium uses explicit `WebDriverWait` and Playwright relies on built-in auto-waiting.
  - Microsoft Edge (`msedge` channel) headless in both frameworks.
  - Isolated test data factory via REST API (`POST /api/Users/`) ensuring zero inter-test dependency.
- **Automated Benchmark Harness (`bench/run.py`)**:
  - Built strictly with Python standard library modules (`argparse`, `subprocess`, `xml.etree.ElementTree`, `statistics`, `json`).
  - Executes each suite $N$ times with `pytest --junitxml`, parsing test durations and failures across runs.
  - Generates machine-readable `results/benchmark.json` and CI summary `results/benchmark.md`.
- **Migration Documentation**:
  - Code-level equivalence table and architectural differences detailed in [`docs/MIGRATION-GUIDE.md`](docs/MIGRATION-GUIDE.md).

---

## 2. Test Coverage & Scenario Mapping

All 8 scenarios are sourced from the verified user flows in `Portfolio-Automation/26-cypress-juice-shop/cypress/e2e`:

| Scenario ID | Test Function Name | Module | Description | Isolation Strategy |
| :---: | :--- | :--- | :--- | :--- |
| **01** | `test_login_valid` | Authentication | Authenticate valid user via UI form and verify session redirect | Disposable user created via API |
| **02** | `test_login_invalid` | Authentication | Reject invalid credentials and verify `.error` feedback message | Anonymous / Non-existent |
| **03** | `test_user_registration` | Authentication | Fill registration form, select security question, submit, verify redirect | Unique UUID timestamped email |
| **04** | `test_search_with_results` | Catalog | Search for `apple` and verify matching product cards rendered | Read-only search query |
| **05** | `test_search_without_results` | Catalog | Search for non-existent product and verify `emptyState` card | Read-only search query |
| **06** | `test_add_to_cart` | Basket | Add product to shopping basket and verify item presence | Dedicated authenticated session |
| **07** | `test_remove_from_cart` | Basket | Add product to basket, remove it, and verify basket is empty | Dedicated authenticated session |
| **08** | `test_language_change` | Localization | Open language menu, switch to German, verify `Konto` label in navbar | Dynamic UI language switch |

---

## 3. Architecture & Target Design

```mermaid
flowchart TD
    subgraph CI["GitHub Actions Pipeline (.github/workflows/39-selenium-to-playwright-migration.yml)"]
        G1["Unit Tests: tests/test_bench.py"] --> G2["Docker Compose Up (127.0.0.1:3000)"]
        G2 --> G3["Benchmark Harness: bench/run.py --runs N"]
        G3 --> G4["Publish Step Summary (results/benchmark.md)"]
        G4 --> G5["Upload Artifacts (results/) & Teardown"]
    end

    subgraph Frameworks["Automated Test Suites (Python + Pytest)"]
        SEL["legacy_selenium/\n- Selenium 4.52.0\n- WebDriverWait explicit waits\n- Edge Headless\n- Page Objects"]
        PW["migrated_playwright/\n- Playwright 1.65.0\n- Auto-waiting Locators\n- Edge Channel (msedge)\n- Page Objects"]
    end

    subgraph SUT["System Under Test (Containerized SUT)"]
        APP["OWASP Juice Shop (v17.1.1)"]
        DB[("In-Memory SQLite")]
    end

    G3 --> SEL
    G3 --> PW
    SEL -->|HTTP / WebDriver| APP
    PW -->|CDP / WebSocket| APP
```

---

## 4. Getting Started & Local Execution

### Prerequisites

- Python `3.12+` and `uv` (or `py -m venv`)
- Docker & Docker Compose
- Microsoft Edge browser installed locally

### Installation

```bash
# Navigate to the project directory
cd Portfolio-Automation/39-selenium-to-playwright-migration

# Create virtual environment and install exact pinned dependencies
uv venv .venv
uv pip install -r requirements.txt
```

### Starting the SUT

```bash
# Start Juice Shop container and wait until healthy on port 3000
docker compose up -d --wait
```

### Running Test Suites Independently

```bash
# Run unit tests for benchmark harness
.venv\Scripts\python.exe -m pytest tests -q

# Run legacy Selenium 4 test suite
.venv\Scripts\python.exe -m pytest legacy_selenium -q

# Run migrated Playwright test suite
.venv\Scripts\python.exe -m pytest migrated_playwright -q
```

### Running the Comparative Benchmark

```bash
# Run 3 repeated iterations per suite (or --runs 10 for full sample)
.venv\Scripts\python.exe bench\run.py --runs 3

# View benchmark report
type results\benchmark.md
```

### Teardown

```bash
# Stop and remove container
docker compose down -v
```

---

## 5. Results

<!-- BENCH -->
Numbers come from [CI run 42949800072](https://github.com/valarcon1226/qa-automation-portfolio/actions/runs/42949800072) on a GitHub-hosted `ubuntu-latest` runner, 5 repetitions per suite. Every run publishes a fresh table in its job summary.

- **Timestamp**: 2026-11-11T03:07:19.431872+00:00
- **Repetitions per Suite**: 5
- **Python Interpreter**: 3.12.16
- **Browser**: Microsoft Edge (headless)

### 1. Suite-Level Summary

| Metric | Legacy Selenium 4 | Migrated Playwright | Delta / Comparison |
| :--- | :---: | :---: | :---: |
| **Lines of Code (code lines)** | 345 | 304 | -11.9% |
| **Total Lines (with comments)** | 453 | 397 | - |
| **Python Files** | 11 | 11 | - |
| **Median Suite Duration** | 24.641 s | 14.902 s | **1.65x faster** |
| **P95 Suite Duration** | 166.725 s | 15.788 s | - |

### 2. Per-Scenario Failure Rate & Durations

| Scenario | Selenium Fail Rate | Selenium Median | Playwright Fail Rate | Playwright Median | Speedup |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `test_add_to_cart` | 20.0% (1/5) | 2.573 s | 0.0% (0/5) | 1.322 s | 1.95x |
| `test_language_change` | 0.0% (0/5) | 1.905 s | 0.0% (0/5) | 1.268 s | 1.50x |
| `test_login_invalid` | 0.0% (0/5) | 2.227 s | 0.0% (0/5) | 0.870 s | 2.56x |
| `test_login_valid` | 20.0% (1/5) | 2.289 s | 0.0% (0/5) | 1.705 s | 1.34x |
| `test_remove_from_cart` | 0.0% (0/5) | 3.233 s | 0.0% (0/5) | 1.495 s | 2.16x |
| `test_search_with_results` | 0.0% (0/5) | 2.076 s | 0.0% (0/5) | 0.932 s | 2.23x |
| `test_search_without_results` | 0.0% (0/5) | 2.148 s | 0.0% (0/5) | 0.922 s | 2.33x |
| `test_user_registration` | 20.0% (1/5) | 7.158 s | 0.0% (0/5) | 6.308 s | 1.13x |

### 3. Reading the numbers

- Suite duration: Playwright is **1.65x** relative to Selenium 4 on the same 8 scenarios.
- Code size: **-11.9%** executable lines after the migration, same Page Object structure.
- The Selenium suite starts one Edge process per test; the Playwright suite starts Edge once and opens a fresh context per test. Both isolate tests, and that difference is part of the speedup.
- A failure rate of 0 over a few runs does not prove a suite is stable; raise --runs to look for intermittent failures.

The three Selenium failures fell in two of the five repetitions. Repetition 1 had a driver session that timed out while starting Edge (120 s, which is why the P95 is far above the median) and an `ElementClickInterceptedException`; repetition 5 had a `StaleElementReferenceException`. The Playwright suite hit none of them. Five repetitions are a small sample: the failure rates are an observation, not an estimate.

---

## 6. Documentation Index

- [`docs/MIGRATION-GUIDE.md`](docs/MIGRATION-GUIDE.md): Code equivalence table (synchronization, locators, fixtures, session handling) and analysis of what did not improve.
- [GitHub Actions Workflow](file:///.github/workflows/39-selenium-to-playwright-migration.yml): Automated CI workflow executing repeated benchmark runs against live containerized SUT.
