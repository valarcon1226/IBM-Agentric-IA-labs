# Valentina Alarcon · QA automation portfolio

I am a QA automation engineer. This repository collects the work I use to show how I test: suites against real open-source systems, framework projects in several stacks, and automation services built around small-business use cases.

Every numbered folder is one project. [`PROJECTS.md`](PROJECTS.md) is the index, with the status and evidence of each one.

## Start here: QA on real open-source systems

Each suite runs the real product in containers and checks what tends to break in production: concurrency, retries, partial failures, pagination under writes and version upgrades. Every project README says where its numbers come from and what its limits are.

| Project | System under test | What it covers | CI |
|---|---|---|---|
| [34 · Order integrity](34-commerce-order-integrity/) | Saleor 3.20 | Pagination properties, checkout retries through a fault proxy, a 50-buyer stock race, webhook delivery under failures, a 3.19 → 3.20 upgrade with checksums | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/34-commerce-order-integrity.yml/badge.svg?branch=main) |
| [35 · Document intake](35-document-intake-pipeline/) | Paperless-ngx 2.14.7 | A 500-document burst with broker faults, pagination ties, search latency, a 2.14.6 → 2.14.7 migration diff, an accessibility scan | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/35-document-intake-pipeline.yml/badge.svg?branch=main) |
| [36 · CDC replication](36-cdc-data-replication/) | Postgres → Debezium → Redpanda → Postgres | Lag under load, a slow sink, a killed worker, poison records, live schema changes and a 1M-row snapshot, each verified by a reconciler that has its own tests | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/36-cdc-data-replication.yml/badge.svg?branch=main) |
| [37 · Identity and access](37-identity-access/) | Keycloak 26 | OIDC with PKCE and negative cases, token replay, TOTP and lockout on three browsers, an SMTP outage, load shedding, a 25 → 26 upgrade | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/37-identity-access.yml/badge.svg?branch=main) |
| [38 · LLM platform](38-llm-platform-evals/) | LiteLLM + Open WebUI + Ollama | Spend and budget accounting, rate limits, retries, a stream cut observed at three layers, and a RAG evaluation with a pre-registered protocol | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/38-llm-platform-evals.yml/badge.svg?branch=main) |

## Test automation frameworks

| Project | Stack | Notes | CI |
|---|---|---|---|
| [24 · ParaBank](24-playwright-ts-parabank/) | Playwright, TypeScript | UI flows verified against the REST API, page objects as fixtures, a table of designed versus automated scenarios | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/24-playwright-ts-parabank.yml/badge.svg?branch=main) |
| [26 · Juice Shop](26-cypress-juice-shop/) | Cypress, TypeScript | Login, catalog, checkout, API and network-failure tests | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/26-cypress-juice-shop.yml/badge.svg?branch=main) |
| [27 · API contract quality](27-api-contract-quality/) | Pact, Schemathesis, Newman | Consumer contracts and fuzzing against my own services; it found two defects in project 13, fixed since | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/27-api-contract-quality.yml/badge.svg?branch=main) |
| [39 · Selenium to Playwright](39-selenium-to-playwright-migration/) | Python, Selenium 4, Playwright | The same 8 scenarios in both tools against Juice Shop, with suite duration and intermittent failures measured over repeated runs in CI | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/39-selenium-to-playwright-migration.yml/badge.svg?branch=main) |
| [40 · Android app](40-mobile-appium-android/) | Appium 3, Python, UiAutomator2 | 7 scenarios on an open-source Android app, run on the GitHub Actions emulator, with screenshot, page source and logcat kept on failure | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/40-mobile-appium-android.yml/badge.svg?branch=main) |
| [41 · Performance gate](41-performance-k6/) | k6, Docker | Load, spike and forged-signature scenarios against the order service of project 20, with thresholds, a baseline comparison and a run-to-run trend. It found a race on simultaneous deliveries, fixed since | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/41-performance-k6.yml/badge.svg?branch=main) |
| [19 · Java suite](19-qa-java-suite/) | Java 21, Selenium, Cucumber, REST Assured, Allure | 35 cases, page objects shared by JUnit tests and Cucumber steps | Runs in Docker |
| [15 · Python suite](15-qa-showcase/) | Python, Playwright, httpx | API and UI tests, including five that pin known bugs of the demo site | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/15-qa-showcase.yml/badge.svg?branch=main) |
| [42 · Test case generator](42-test-case-generator-evals/) | Python, pydantic, Ollama | A local model writes test cases from a requirement and six deterministic metrics grade them against thresholds fixed in advance. A 4B model met 3 of 5 on the held-out split | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/42-test-case-generator-evals.yml/badge.svg?branch=main) |
| [18 · Agent evals](18-mcp-agent-evals/) | MCP, pytest, Ollama | A tool server plus 30 evaluation cases for a tool-using agent, run with a stub and with a local 4B model, before and after a fix to the tool schemas. The README reads every failed case | Local |

## Automation services

Backend and automation projects, each with code, tests and a README that states its limits. The full list with evidence is in the [portfolio index](PROJECTS.md). A few to start with:

- [13 · WhatsApp restaurant assistant](13-whatsapp-restaurant-assistant/) with its [web chat widget](22-web-chat-widget/)
- [20 · E-commerce order automation](20-ecommerce-order-automation/): signed webhooks, idempotency and an admin panel
- [14 · n8n automation pack](14-n8n-automation-pack/), tested against a real n8n
- [04 · Data cleaning API](04-data-cleaning-api/), [11 · Monitoring](11-monitoring-dashboard/) and [12 · CI/CD pipeline](12-ci-cd-pipeline/)

## Other work in this repository

- [`YouTube-RAG-Analyzer`](YouTube-RAG-Analyzer/): turns videos into fact-checked notes using free LLM tiers.
- [`doc_ingest`](doc_ingest/): local document ingestion and question answering with Ollama.
- [`jobHunter`](jobHunter/): my own job-search automation. A personal tool, still without a README.
- [`Homelab`](Homelab/): notes on the server that runs my automations.
- Coursework from the IBM RAG and Agentic AI certificate, kept for reference: [`AI-Agents-Fundamentals`](AI-Agents-Fundamentals/), [`Advanced-RAG-Techniques`](Advanced-RAG-Techniques/), [`Candidate-Filter`](Candidate-Filter/), [`Enterprise-QA-Agent`](Enterprise-QA-Agent/), [`Food-Search-Chatbot`](Food-Search-Chatbot/) and [`Multimodal-Generators`](Multimodal-Generators/). They are short lab scripts that need IBM watsonx or OpenAI credentials.

## How to read the evidence

- A CI badge shows the last run on `main`. Workflows are in [`.github/workflows`](.github/workflows/). The heavier suites (resilience, migration, performance) run in scheduled nightly jobs.
- Each findings document separates what was measured from the explanation, and says so when a cause is not confirmed.
- Versions of the systems under test are pinned in every compose file, so a result can be reproduced.
