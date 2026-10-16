# Comparative Technical Analysis: Cypress vs. Playwright

This document provides a factual, evidence-based architectural comparison between **Cypress** and **Playwright**. Both frameworks are evaluated using the identical user journey against OWASP Juice Shop:

> **Target Flow**: Authenticate via UI credentials and add the first catalog product to the shopping basket.

---

## 1. Code Comparison: The Same Workflow

### Cypress Implementation (TypeScript)

```typescript
describe('Juice Shop Purchase Flow', () => {
  it('Login and Add Product to Basket', () => {
    // 1. Visit with pre-dismissed cookie and welcome banners
    cy.setCookie('welcomebanner_status', 'dismiss');
    cy.setCookie('cookieconsent_status', 'dismiss');
    cy.visit('/#/login');

    // 2. Intercept network requests for synchronization
    cy.intercept('POST', '**/rest/user/login').as('loginReq');
    cy.intercept('POST', '**/api/BasketItems/**').as('addToBasketReq');

    // 3. Perform login
    cy.get('#email').type('testuser@juice-sh.op');
    cy.get('#password').type('TestPassword123!');
    cy.get('#loginButton').should('be.enabled').click();

    // 4. Synchronize on login response and redirect
    cy.wait('@loginReq').its('response.statusCode').should('eq', 200);
    cy.url().should('not.include', '/#/login');

    // 5. Add product to basket
    cy.get('button[aria-label="Add to Basket"]').first().click();
    cy.wait('@addToBasketReq').its('response.statusCode').should('eq', 200);

    // 6. Verify floating notification
    cy.get('snack-bar-container', { timeout: 10000 }).should('contain.text', 'into basket');
  });
});
```

### Playwright Implementation (TypeScript)

```typescript
import { test, expect } from '@playwright/test';

test('Login and Add Product to Basket', async ({ page, context }) => {
  // 1. Set cookies in browser context prior to navigation
  await context.addCookies([
    { name: 'welcomebanner_status', value: 'dismiss', domain: '127.0.0.1', path: '/' },
    { name: 'cookieconsent_status', value: 'dismiss', domain: '127.0.0.1', path: '/' },
  ]);

  // 2. Set up request listeners
  const loginPromise = page.waitForResponse(
    (res) => res.url().includes('/rest/user/login') && res.status() === 200,
  );
  const basketPromise = page.waitForResponse(
    (res) => res.url().includes('/api/BasketItems') && res.status() === 200,
  );

  // 3. Navigate and authenticate
  await page.goto('http://127.0.0.1:8641/#/login');
  await page.locator('#email').fill('testuser@juice-sh.op');
  await page.locator('#password').fill('TestPassword123!');
  await page.locator('#loginButton').click();

  // 4. Await network resolution
  await loginPromise;
  await expect(page).not.toHaveURL(/.*#\/login/);

  // 5. Add product to basket
  await page.locator('button[aria-label="Add to Basket"]').first().click();
  await basketPromise;

  // 6. Verify notification
  await expect(page.locator('snack-bar-container')).toContainText('into basket');
});
```

---

## 2. In-Depth Comparative Dimensions

### 1. Auto-Waiting & Execution Model

- **Cypress**:
  - Uses an asynchronous command queue (`cy.get()`, `cy.click()`). Commands do not return standard ES Promises; instead, they enqueue execution steps managed by the Cypress runner.
  - Automatically retries assertions chained with `.should()` until DOM elements appear and satisfy conditions up to `defaultCommandTimeout` (default 4000ms).
  - Runs directly inside the browser's execution loop (inside an iframe), giving synchronous access to DOM nodes, window objects, and local storage.
- **Playwright**:
  - Uses native JavaScript `async` / `await` syntax. Every action is a genuine Promise.
  - Performs comprehensive **actionability checks** before every interaction: verifies element is attached to DOM, visible, stable (not animating), enabled, and un-obscured by other overlays.
  - Controls the browser out-of-process via Chrome DevTools Protocol (CDP) / Firefox Marionette / WebKit protocols, completely decoupling test execution from the webpage runtime.

### 2. Network Interception & Traffic Control

- **Cypress (`cy.intercept`)**:
  - Intercepts requests by overriding `window.fetch` and `XMLHttpRequest` inside the browser window.
  - Supports route aliasing (`.as('name')`), fixture mocking, header/body mutation, and response delay injection (`res.delay = 1000`).
  - Seamlessly integrates into command queue with `cy.wait('@alias')`.
- **Playwright (`page.route` / `page.waitForResponse`)**:
  - Intercepts at the browser engine protocol layer before network packets leave the process.
  - Intercepts WebSockets, SSE, and service workers natively.
  - Supports HAR file recording and playback for deterministic offline replay (`page.routeFromHAR()`).

### 3. Multi-Tab, Multi-Window & Domain Switching

- **Cypress**:
  - **Limitation**: Cannot interact with multiple browser tabs or popup windows natively. If an application opens a new window (`window.open` or `target="_blank"`), tests must either strip the `target` attribute (`cy.invoke('removeAttr', 'target')`) or stub the window method.
  - Cross-origin navigation across different superdomains within a single test requires the `cy.origin()` wrapper.
- **Playwright**:
  - **Native Support**: Full first-class support for multiple tabs and popup windows within a single browser context (`context.waitForEvent('page')`).
  - Allows simultaneous multi-user, multi-context interactions (e.g. testing an instant chat conversation between User A and User B in two isolated contexts simultaneously).

### 4. Parallelism & CI Scaling

- **Cypress**:
  - Parallel test distribution across CI machines requires either **Cypress Cloud** (commercial SaaS) or third-party orchestration tools (e.g. Sorry Cypress).
  - Out-of-the-box local and free CI runs execute serially unless manually partitioned with custom shell scripts.
- **Playwright**:
  - Provides native **sharding** built into the core CLI (`npx playwright test --shard=1/4`).
  - Can distribute tests across unlimited GitHub Actions runners for free without any third-party subscription or cloud dependency.

### 5. Debugging & Developer Experience (DX)

- **Cypress**:
  - **Interactive App Runner**: World-class visual debugger. Provides **Time Travel**, hovering over each step in the command log to inspect the exact DOM snapshot at that millisecond.
  - Debugger statements and `cy.pause()` allow live browser DOM inspection in Chrome/Edge DevTools.
- **Playwright**:
  - **Trace Viewer**: Standalone GUI and web viewer (`playwright.dev/trace`) recording DOM snapshots, network waterfalls, screencasts, and action logs. Can be shared as zip artifacts and debugged post-mortem without re-running the test.
  - Full integration with VS Code extension featuring interactive breakpoint debugging and selector pickers.

---

## 3. Decision Matrix

| Dimension              |                    Cypress                     |                Playwright                | Evidence / Notes                                                       |
| :--------------------- | :--------------------------------------------: | :--------------------------------------: | :--------------------------------------------------------------------- |
| **Language & Typing**  |                TypeScript / JS                 |   TypeScript / JS / Python / Java / C#   | Playwright offers multi-language bindings; Cypress is JS/TS only.      |
| **Execution Context**  |              In-browser (iframe)               |    Out-of-process (DevTools Protocol)    | Cypress has direct DOM access; Playwright avoids in-page memory leaks. |
| **Multi-tab & Popups** |              Workarounds required              |       Native (`context.newPage()`)       | Cypress cannot switch tabs; Playwright handles tabs natively.          |
| **Browser Engines**    | Chromium, Edge, Firefox, WebKit (experimental) | Chromium, Edge, Firefox, WebKit (native) | Playwright bundles true WebKit engine on Windows/Linux.                |
| **CI Sharding**        |             Requires Cypress Cloud             |       Free native CLI (`--shard`)        | Playwright shards natively in GitHub Actions with zero cost.           |
| **Debugging**          |          Interactive Time Travel App           |      Trace Viewer & VS Code plugin       | Both provide industry-leading debugging capabilities.                  |
