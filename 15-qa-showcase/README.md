# 15 - QA Showcase

A pytest suite with two layers: API tests for Restful Booker and Playwright UI tests for SauceDemo,
plus the QA documents that go with them (test plan, bug reports with screenshots).

It shows how I split a suite into page objects and tests, and how I record known product bugs: five
UI tests are marked `xfail(strict=True)` against a bug id, so the suite stays green while the bug
exists and fails the day the bug is fixed.

## Run it

```bash
py -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

The UI tests run on Microsoft Edge, so Edge must be installed (it is preinstalled on Windows).
Elsewhere, run `playwright install msedge` first.

## Results

26 tests are collected (`pytest --collect-only -q`): 8 API and 18 UI.
Expected outcome: 21 passed and 5 xfailed. The run writes `reports/SUMMARY.md` (counts and the xfail
list) and `reports/report.html`.

## Structure

- `tests/api/test_restful_booker.py`: 5 CRUD tests and 3 negative tests (bad token, unknown id, missing body).
- `tests/ui/`: login, inventory, cart and checkout tests, run for `standard_user` and `problem_user`.
- `tests/pages/`: page objects (`base_page`, `login_page`, `inventory_page`, `cart_page`, `checkout_page`).
- `tests/data.py`: users and test data. `tests/conftest.py`: writes `reports/SUMMARY.md`.
- `docs/TEST-PLAN.md`: test plan. `docs/BUG-REPORTS.md`: bug reports (written in Spanish).
- `docs/evidence/`: one screenshot per bug.
- `postman/RestfulBooker.postman_collection.json`: the same API calls as a Postman collection.
- `pyproject.toml`: pinned dependencies, pytest options (Edge, HTML report, traces and screenshots on failure) and ruff settings.

## Bugs pinned by xfail tests

All five happen with `problem_user` on SauceDemo.

| Bug | What the test checks | Test | Report | Evidence |
|---|---|---|---|---|
| QA-102 | Sorting products works | `tests/ui/test_inventory.py::test_inventory_sorting_problem` | [report](docs/BUG-REPORTS.md) | [image](docs/evidence/qa-102.png) |
| QA-103 | Product images load correctly | `tests/ui/test_inventory.py::test_inventory_images_problem` | [report](docs/BUG-REPORTS.md) | [image](docs/evidence/qa-103.png) |
| QA-104 | Every Add to cart button works | `tests/ui/test_inventory.py::test_add_all_items_problem` | [report](docs/BUG-REPORTS.md) | [image](docs/evidence/qa-104.png) |
| QA-105 | Last name is kept in the checkout form | `tests/ui/test_checkout.py::test_successful_checkout[problem]` | [report](docs/BUG-REPORTS.md) | [image](docs/evidence/qa-105.png) |
| QA-106 | Remove from the inventory page works | `tests/ui/test_inventory.py::test_remove_item_from_cart[problem]` | [report](docs/BUG-REPORTS.md) | [image](docs/evidence/qa-106.png) |

## Limits

- The tests depend on two public demo sites, saucedemo.com and restful-booker.herokuapp.com.
  If either is down or slow, the run fails for reasons unrelated to the code.
- The API tests create the bookings they use (fixture `create_booking`) and add a short sleep between tests (`slow_down_tests`) to be gentle with the shared demo API.
- UI tests run only on Microsoft Edge; no other browser is configured.
- The bug reports and the "bugs" they describe are SauceDemo's intentional `problem_user` behavior, not defects in a real product.
- CI: `.github/workflows/15-qa-showcase.yml` at the repository root (push on this folder, or manual run).
