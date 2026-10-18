"""Unit tests for assert_target."""

from __future__ import annotations

from pathlib import Path

import pytest
from qa_common.targets import assert_target


def test_assert_target_success(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.toml"
    targets_file.write_text(
        """
[targets]
checkout_p95_ms = 1500
webhook_delivery_percent = 100
""",
        encoding="utf-8",
    )

    # Should pass without error
    assert_target("checkout_p95_ms", 1200, targets_path=targets_file)
    assert_target("checkout_p95_ms", 1500, targets_path=targets_file)
    assert_target("webhook_delivery_percent", 100, targets_path=targets_file)


def test_assert_target_failure_upper_bound(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.toml"
    targets_file.write_text(
        """
[targets]
checkout_p95_ms = 1500
""",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError) as exc_info:
        assert_target("checkout_p95_ms", 1600, targets_path=targets_file)

    msg = str(exc_info.value)
    assert "checkout_p95_ms" in msg
    assert "1500" in msg
    assert "1600" in msg


def test_assert_target_failure_lower_bound(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.toml"
    targets_file.write_text(
        """
[targets]
recovery_percent = 100
""",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError) as exc_info:
        assert_target("recovery_percent", 95, targets_path=targets_file)

    msg = str(exc_info.value)
    assert "recovery_percent" in msg
    assert "100" in msg
    assert "95" in msg
