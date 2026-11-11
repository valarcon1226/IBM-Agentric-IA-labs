"""Pytest configuration and fixtures for Selenium 4 suite."""

from __future__ import annotations

import os
import pytest
from selenium import webdriver
from selenium.webdriver.edge.options import Options


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://127.0.0.1:3000")


@pytest.fixture
def driver(base_url: str):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    edge_driver = webdriver.Edge(options=options)
    edge_driver.implicitly_wait(0)  # Strict explicit waits only

    # Pre-seed banner dismissal cookies on initial origin load
    edge_driver.get(f"{base_url}/#/")
    try:
        edge_driver.add_cookie({"name": "welcomebanner_status", "value": "dismiss"})
        edge_driver.add_cookie({"name": "cookieconsent_status", "value": "dismiss"})
    except Exception:
        pass

    yield edge_driver

    try:
        edge_driver.quit()
    except Exception:
        pass
