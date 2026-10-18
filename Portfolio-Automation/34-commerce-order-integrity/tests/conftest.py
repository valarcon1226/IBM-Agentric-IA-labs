"""Shared pytest fixtures and configuration for Saleor test suite."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --repeat-each as an alias to pytest-repeat's --count option."""
    try:
        parser.addoption(
            "--repeat-each",
            action="store",
            default=None,
            type=int,
            dest="repeat_each",
            help="Number of times to repeat each test (alias for pytest-repeat --count)",
        )
    except ValueError:
        pass


def pytest_configure(config: pytest.Config) -> None:
    """Propagate --repeat-each value to config.option.count for pytest-repeat."""
    repeat_each = getattr(config.option, "repeat_each", None)
    if repeat_each is not None:
        config.option.count = repeat_each
