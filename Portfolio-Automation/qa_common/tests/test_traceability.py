"""Unit tests for traceability generation."""

from __future__ import annotations

import pytest

pytest_plugins = ["pytester"]


def test_traceability_generation(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use isolated test directory as working directory
    monkeypatch.chdir(pytester.path)

    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.req("REQ-CHK-001")
        def test_checkout_validation():
            assert True

        @pytest.mark.req("REQ-STK-002")
        def test_stock_reservation():
            assert True
        """
    )

    result = pytester.runpytest()
    result.assert_outcomes(passed=2)

    trace_file = pytester.path / "docs" / "TRACEABILITY.md"
    assert trace_file.is_file()

    content = trace_file.read_text(encoding="utf-8")
    assert "# Traceability Matrix" in content
    assert "REQ-CHK-001" in content
    assert "REQ-STK-002" in content
    assert "PASSED" in content


def test_traceability_xfail_and_merge(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(pytester.path)
    pytester.makepyfile(
        test_a="""
        import pytest

        @pytest.mark.req("REQ-A-001")
        @pytest.mark.xfail(strict=True, reason="known defect")
        def test_known_defect():
            assert False
        """,
        test_b="""
        import pytest

        @pytest.mark.req("REQ-B-001")
        def test_other():
            assert True
        """,
    )
    pytester.runpytest("test_a.py").assert_outcomes(xfailed=1)
    pytester.runpytest("test_b.py").assert_outcomes(passed=1)

    content = (pytester.path / "docs" / "TRACEABILITY.md").read_text(encoding="utf-8")
    assert "| REQ-A-001 | `test_a.py::test_known_defect` | XFAIL |" in content
    assert "| REQ-B-001 | `test_b.py::test_other` | PASSED |" in content
