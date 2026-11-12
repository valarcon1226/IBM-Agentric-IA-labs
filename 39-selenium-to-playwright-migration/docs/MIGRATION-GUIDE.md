# Technical Migration Guide: Selenium 4 to Playwright

This document provides a concrete, code-level reference for migrating automated test suites from **Selenium 4** to **Playwright** in Python, based directly on the implementation of the 8 end-to-end scenarios against OWASP Juice Shop in `legacy_selenium/` and `migrated_playwright/`.

---

## 1. Code Equivalence Table

| Domain / Concept | Selenium 4 (`legacy_selenium/`) | Playwright (`migrated_playwright/`) | Migration Takeaway |
| :--- | :--- | :--- | :--- |
| **Browser Setup & Launch** | `options = Options()`<br>`options.add_argument("--headless=new")`<br>`driver = webdriver.Edge(options=options)` | `@pytest.fixture(scope="session")`<br>`def browser_type_launch_args(args):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return {**args, "channel": "msedge"}` | Playwright natively binds to Edge via the `channel="msedge"` launch argument without requiring separate WebDriver binaries or manual driver matching. |
| **Context & Cookie Pre-seeding** | `driver.get(f"{base_url}/#/")`<br>`driver.add_cookie({"name": "k", "value": "v"})` | `context.add_cookies([`<br>&nbsp;&nbsp;&nbsp;&nbsp;`{"name": "k", "value": "v", "url": base_url}`<br>`])` | Playwright supports setting cookies on the `BrowserContext` before navigating to the page, avoiding flash-of-banner dialogs. |
| **Element Locators** | `By.ID, "email"`<br>`By.CSS_SELECTOR, "mat-card"`<br>`By.TAG_NAME, "mat-table"` | `page.locator("#email")`<br>`page.locator("mat-card")`<br>`page.locator("mat-table")` | Playwright unifies locator syntax into CSS and built-in pseudo-classes (e.g. `:has-text()`, `:visible`), eliminating multiple enum imports. |
| **Click Action & Auto-Waiting** | `el = wait.until(EC.element_to_be_clickable((By.ID, "loginButton")))`<br>`el.click()` | `page.locator("#loginButton").click()` | Playwright performs built-in actionability checks (visible, stable, enabled, clickable) before executing clicks, removing boilerplate wait loops. |
| **Input & Text Entry** | `el = wait.until(EC.element_to_be_clickable((By.ID, "email")))`<br>`el.clear()`<br>`el.send_keys("user@test.com")` | `page.locator("#email").fill("user@test.com")` | `fill()` automatically clears existing input and emits proper change/input events. |
| **Key Press (Enter/Submit)** | `from selenium.webdriver.common.keys import Keys`<br>`el.send_keys(Keys.ENTER)` | `page.locator("#searchQuery input").press("Enter")` | Native string key names without separate Key class imports. |
| **Angular Overlay Backdrops** | `def no_blocking(d):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return all(not p.is_displayed() for p in d.find_elements(By.CSS_SELECTOR, ".cdk-overlay-pane"))`<br>`wait.until(no_blocking)` | `page.locator("mat-select").click()`<br>`page.locator("mat-option").first.click()`<br>`# Handled automatically` | Selenium throws `ElementClickInterceptedException` when Angular CDK overlay backdrops fade slowly; Playwright waits for overlapping animations automatically. |
| **URL Navigation Assertion** | `wait.until(EC.url_contains("/#/search"))` | `page.wait_for_url("**/#/search")` | Cleaner glob matching support in Playwright. |
| **Element Disappearance** | `wait.until(EC.invisibility_of_element_located((By.TAG_NAME, "mat-row")))` | `page.wait_for_function("document.querySelectorAll('mat-row').length === 0")`<br>or `locator.wait_for(state="detached")` | Flexible DOM state assertions without stale element references. |
| **Teardown & Cleanup** | `driver.quit()` | Automatic via pytest-playwright fixture lifecycle (`page.close()`, `context.close()`). | Contexts are fully isolated and clean up automatically per test without residual browser processes. |

---

## 2. Page Object Model Translation

### Selenium 4 Implementation (`legacy_selenium/pages/login_page.py`)
```python
class LoginPage(BasePage):
    EMAIL_INPUT = (By.ID, "email")
    PASSWORD_INPUT = (By.ID, "password")
    LOGIN_BUTTON = (By.ID, "loginButton")

    def login(self, email: str, password: str, wait_for_success: bool = True) -> None:
        email_el = self.wait.until(EC.element_to_be_clickable(self.EMAIL_INPUT))
        email_el.clear()
        email_el.send_keys(email)

        pwd_el = self.wait.until(EC.element_to_be_clickable(self.PASSWORD_INPUT))
        pwd_el.clear()
        pwd_el.send_keys(password)

        login_btn = self.wait.until(EC.element_to_be_clickable(self.LOGIN_BUTTON))
        login_btn.click()

        if wait_for_success:
            self.wait.until(EC.url_contains("/#/search"))
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "mat-card")))
```

### Playwright Implementation (`migrated_playwright/pages/login_page.py`)
```python
class LoginPage(BasePage):
    EMAIL_INPUT = "#email"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#loginButton"

    def login(self, email: str, password: str, wait_for_success: bool = True) -> None:
        self.page.locator(self.EMAIL_INPUT).fill(email)
        self.page.locator(self.PASSWORD_INPUT).fill(password)
        self.page.locator(self.LOGIN_BUTTON).click()

        if wait_for_success:
            self.page.wait_for_url("**/#/search")
            self.page.locator("mat-card").first.wait_for(state="visible")
```

---

## 3. What Did NOT Improve

While Playwright dramatically simplified synchronization code and accelerated execution speeds, migration is not a silver bullet. The following areas did **not** improve:

1. **System Under Test (SUT) Response Latency**:
   - Backend database queries, Express.js route processing, and SQLite disk I/O take the exact same time regardless of whether Selenium or Playwright initiates the request.
   - Initial application hydration of the Angular 14 single-page application remains identical.

2. **DOM Selector Fragility**:
   - Using fragile or overly generic CSS classes (e.g. non-semantic utility classes) leads to broken tests in Playwright just as easily as in Selenium. Locators must still be anchored to semantic attributes (`id`, `aria-label`, data attributes).

3. **Angular Material Animation Durations**:
   - Opening modal menus, dialog expansions, and snackbar notifications depend on CSS transitions defined in the Angular theme. While Playwright waits for element stability automatically, the animation itself takes the same number of milliseconds to complete.

4. **Test Data Lifecycle Requirements**:
   - Flakiness caused by shared test data or conflicting state in the database is not mitigated by the test runner. Both suites require strict data isolation (disposable users provisioned per test via the API) to avoid cascade failures.

5. **External Environmental Instability**:
   - Docker container restarts, network timeouts, and resource contention on CI runners affect Playwright runs with the exact same severity as Selenium runs.
