# Test Strategy — OWASP Juice Shop Quality Engineering

## 1. Quality Objectives & Scope

This test automation framework provides automated regression and smoke testing for OWASP Juice Shop (`v17.1.1`). The primary objectives are:

1. Ensure the core e-commerce transactional loop (Register &rarr; Login &rarr; Catalog Search &rarr; Basket &rarr; Address &rarr; Payment &rarr; Order Completion) remains fully operational.
2. Verify resilience against network degradation and backend server failures (500 errors, delayed responses) using `cy.intercept`.
3. Validate API contract integrity across core customer and catalog endpoints.
4. Maintain a zero-flakiness policy through deterministic state seeding and dynamic waiting (no arbitrary `cy.wait(ms)` sleeps).

---

## 2. Test Pyramid & Automation Levels

```
               / \
              /   \
             / E2E \       <-- Full User Journeys: Registration, Checkout Flow, Reviews (Cypress Edge/Firefox)
            /-------\
           / Network \     <-- Fault Injection & Latency Simulation (cy.intercept)
          /-----------\
         / Integration \   <-- REST API Contracts, JWT Auth, Basket Seeding (cy.request)
        /---------------\
       /    Component    \ <-- Explaining Architectural Applicability (see Section 3)
      /-------------------\
```

### Component Testing Evaluation

The task specifies: _"y al menos un component test de un componente propio sencillo o, si no aplica, explica por qué."_

**Architectural Rationale on Component Testing Applicability:**

- **What Cypress Component Testing Requires**: Cypress Component Testing (`cypress run --component`) mounts individual Angular, React, Vue, or Svelte component source files directly into a browser harness backed by a local dev server (e.g. Angular CLI, Vite, Webpack). It requires direct access to component TypeScript source code, Angular modules (`NgModule` / Standalone), templates, stylesheets, and dependency injection providers.
- **Why It Does Not Apply to This Project**: OWASP Juice Shop is deployed as a pre-compiled, containerized black-box application (`bkimminich/juice-shop:v17.1.1`). The testing repository is an external, decoupled QA automation framework without access to the upstream Angular build tree or source files.
- **Adopted Engineering Decision**: In accordance with the **Ponytail rule** (simplest thing that works, avoiding speculative or synthetic dummy code solely to satisfy a checkbox), isolated component unit testing belongs in the upstream application repository's build pipeline. In this end-to-end QA portfolio project, frontend validation is performed at the Integration, Network Intercept, and End-to-End levels against the live running container. (For an example of an isolated, standalone custom UI component, see Project 22 `web-chat-widget`).

---

## 3. Browser Policy

In strict compliance with QA guidelines:

- **Primary Browser**: **Microsoft Edge** (`--browser edge` / `channel: "msedge"`). Used for all local verification and default CI runs.
- **Secondary Browser**: **Mozilla Firefox** (`--browser firefox`). Used for cross-browser validation triggered via `workflow_dispatch`.
- **Prohibited Browsers**: Google Chrome and vanilla Chromium are strictly prohibited in configuration and test runners.

---

## 4. State Management & Test Data Strategy

- **Zero Shared Mutable State**: Tests never depend on state left by a previous test.
- **Dynamic Seeding via API**: Test users (`cypress-ui-<timestamp>@juice-sh.op`) and addresses are generated with dynamic timestamps via `cy.registerByApi()` and `cy.loginByApi()`.
- **Session Caching**: `cy.session()` caches authentication tokens and synchronizes both `localStorage` and `sessionStorage` (`bid` basket identifier) to accelerate test execution without repeating UI login keystrokes.
- **Initial Banner Dismissal**: Banners (`welcomebanner_status`, `cookieconsent_status`) are dismissed deterministically via cookies and `onBeforeLoad` lifecycle hooks (`visitWithBannersDismissed()`).

---

## 5. Waiting & Synchronization Policy

- **Zero Arbitrary Sleeps**: Fixed sleeps (`cy.wait(3000)`) are strictly banned by ESLint (`cypress/no-unnecessary-waiting: "error"`).
- **Network-Driven Synchronization**: All asynchronous UI transitions are synchronized by awaiting named route aliases (`cy.wait('@registerRequest')`, `cy.wait('@checkoutRequest')`).
- **DOM State Retries**: Assertions leverage Cypress's built-in automatic retries on element visibility, enabled states, and URL changes.

---

## 6. Continuous Integration (CI) Gating

- **Push Pipeline**: Triggered on changes to `26-cypress-juice-shop/**` and the workflow file:
  1. Strict TypeScript check (`tsc --noEmit`).
  2. ESLint check (`eslint .`).
  3. Prettier check (`prettier --check .`).
  4. Container spin-up (`docker compose up -d --wait`).
  5. Fast smoke suite run (`npx cypress run --browser edge --env grepTags=@smoke`).
  6. Artifact upload on failure (screenshots).
  7. Container tear-down (`docker compose down -v`).
- **Manual Pipeline (`workflow_dispatch`)**: Runs full regression suite across Microsoft Edge and Firefox.
