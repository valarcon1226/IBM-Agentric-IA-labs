"""Pytest configuration and fixtures for Playwright suite."""

from __future__ import annotations

import os
import pytest
from playwright.sync_api import BrowserContext, Page


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://127.0.0.1:3000")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    return {
        **browser_type_launch_args,
        "channel": "msedge",
    }


@pytest.fixture
def page(context: BrowserContext, base_url: str) -> Page:
    # Pre-seed dismissal cookies to avoid banner interference
    context.add_cookies([
        {"name": "welcomebanner_status", "value": "dismiss", "url": base_url},
        {"name": "cookieconsent_status", "value": "dismiss", "url": base_url},
    ])
    pg = context.new_page()
    yield pg
    pg.close()
