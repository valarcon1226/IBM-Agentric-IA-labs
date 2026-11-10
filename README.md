# Valentina Alarcon · QA automation portfolio

I am a QA automation engineer. This repository collects the work I use to show how I test: suites against real open-source systems, framework projects in several stacks, and automation services built around small-business use cases.

Most projects live in [`Portfolio-Automation/`](Portfolio-Automation/), which has its own index with the status and evidence of every project.

## Start here: QA on real open-source systems

Each suite runs the real product in containers and checks what tends to break in production: concurrency, retries, partial failures, pagination under writes and version upgrades. Every project README says where its numbers come from and what its limits are.

| Project | System under test | What it covers | CI |
|---|---|---|---|
| [34 · Order integrity](Portfolio-Automation/34-commerce-order-integrity/) | Saleor 3.20 | Pagination properties, checkout retries through a fault proxy, a 50-buyer stock race, webhook delivery under failures, a 3.19 → 3.20 upgrade with checksums | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/34-commerce-order-integrity.yml/badge.svg?branch=main) |
| [35 · Document intake](Portfolio-Automation/35-document-intake-pipeline/) | Paperless-ngx 2.14.7 | A 500-document burst with broker faults, pagination ties, search latency, a 2.14.6 → 2.14.7 migration diff, an accessibility scan | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/35-document-intake-pipeline.yml/badge.svg?branch=main) |
| [36 · CDC replication](Portfolio-Automation/36-cdc-data-replication/) | Postgres → Debezium → Redpanda → Postgres | Lag under load, a slow sink, a killed worker, poison records, live schema changes and a 1M-row snapshot, each verified by a reconciler that has its own tests | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/36-cdc-data-replication.yml/badge.svg?branch=main) |
| [37 · Identity and access](Portfolio-Automation/37-identity-access/) | Keycloak 26 | OIDC with PKCE and negative cases, token replay, TOTP and lockout on three browsers, an SMTP outage, load shedding, a 25 → 26 upgrade | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/37-identity-access.yml/badge.svg?branch=main) |
| [38 · LLM platform](Portfolio-Automation/38-llm-platform-evals/) | LiteLLM + Open WebUI + Ollama | Spend and budget accounting, rate limits, retries, a stream cut observed at three layers, and a RAG evaluation with a pre-registered protocol | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/38-llm-platform-evals.yml/badge.svg?branch=main) |

## Test automation frameworks

| Project | Stack | Notes | CI |
|---|---|---|---|
| [24 · ParaBank](Portfolio-Automation/24-playwright-ts-parabank/) | Playwright, TypeScript | UI flows verified against the REST API, page objects as fixtures, a table of designed versus automated scenarios | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/24-playwright-ts-parabank.yml/badge.svg?branch=main) |
| [26 · Juice Shop](Portfolio-Automation/26-cypress-juice-shop/) | Cypress, TypeScript | Login, catalog, checkout, API and network-failure tests | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/26-cypress-juice-shop.yml/badge.svg?branch=main) |
| [27 · API contract quality](Portfolio-Automation/27-api-contract-quality/) | Pact, Schemathesis, Newman | Consumer contracts and fuzzing against my own services; it found two defects in project 13, fixed since | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/27-api-contract-quality.yml/badge.svg?branch=main) |
| [19 · Java suite](Portfolio-Automation/19-qa-java-suite/) | Java 21, Selenium, Cucumber, REST Assured, Allure | 35 cases, page objects shared by JUnit tests and Cucumber steps | Runs in Docker |
| [15 · Python suite](Portfolio-Automation/15-qa-showcase/) | Python, Playwright, httpx | API and UI tests, including five that pin known bugs of the demo site | ![CI](https://github.com/valarcon1226/qa-automation-portfolio/actions/workflows/15-qa-showcase.yml/badge.svg?branch=main) |
| [18 · Agent evals](Portfolio-Automation/18-mcp-agent-evals/) | MCP, pytest, Ollama | A tool server plus 30 evaluation cases for a tool-using agent, run with a stub and with a local 4B model. The README reads every failed case | Local |

## Automation services

Backend and automation projects, each with code, tests and a README that states its limits. The full list with evidence is in the [portfolio index](Portfolio-Automation/README.md). A few to start with:

- [13 · WhatsApp restaurant assistant](Portfolio-Automation/13-whatsapp-restaurant-assistant/) with its [web chat widget](Portfolio-Automation/22-web-chat-widget/)
- [20 · E-commerce order automation](Portfolio-Automation/20-ecommerce-order-automation/): signed webhooks, idempotency and an admin panel
- [14 · n8n automation pack](Portfolio-Automation/14-n8n-automation-pack/), tested against a real n8n
- [04 · Data cleaning API](Portfolio-Automation/04-data-cleaning-api/), [11 · Monitoring](Portfolio-Automation/11-monitoring-dashboard/) and [12 · CI/CD pipeline](Portfolio-Automation/12-ci-cd-pipeline/)

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
