"""Deterministic unit tests for each evaluation metric in evals.metrics."""

from __future__ import annotations

from app.models import AcceptanceCriterion, Requirement, TestCase
from evals import metrics


def test_schema_valid_rate_pass() -> None:
    results = [
        {"valid_on_first_try": True},
        {"valid_on_first_try": True},
        {"valid_on_first_try": True},
    ]
    rate = metrics.schema_valid_rate(results)
    assert rate == 1.0
    assert rate >= 0.90  # Pre-registered threshold


def test_schema_valid_rate_fail() -> None:
    # Fails pre-registered threshold (0.90)
    results = [
        {"valid_on_first_try": True},
        {"valid_on_first_try": False},
        {"valid_on_first_try": False},
    ]
    rate = metrics.schema_valid_rate(results)
    assert round(rate, 4) == 0.3333
    assert rate < 0.90


def test_schema_valid_rate_empty() -> None:
    assert metrics.schema_valid_rate([]) == 0.0


def test_declared_coverage_pass() -> None:
    req = Requirement(
        id="REQ-TEST",
        title="Test Feature",
        description="Description",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Criterion 1"),
            AcceptanceCriterion(id="AC-02", text="Criterion 2"),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Smoke test",
            level="smoke",
            steps=["Step 1"],
            expected="Success",
            covers=["AC-01"],
        ),
        TestCase(
            id="TC-02",
            title="Functional test",
            level="functional",
            steps=["Step 2"],
            expected="Success",
            covers=["AC-02"],
        ),
    ]
    cov = metrics.declared_coverage([req], {req.id: cases})
    assert cov == 1.0
    assert cov >= 0.70  # Pre-registered threshold


def test_declared_coverage_fail() -> None:
    # Fails pre-registered threshold (0.70)
    req = Requirement(
        id="REQ-TEST",
        title="Test Feature",
        description="Description",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Criterion 1"),
            AcceptanceCriterion(id="AC-02", text="Criterion 2"),
            AcceptanceCriterion(id="AC-03", text="Criterion 3"),
            AcceptanceCriterion(id="AC-04", text="Criterion 4"),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Only covers AC-01",
            level="smoke",
            steps=["Step 1"],
            expected="Success",
            covers=["AC-01"],
        ),
    ]
    cov = metrics.declared_coverage([req], {req.id: cases})
    assert cov == 0.25
    assert cov < 0.70


def test_verified_coverage_pass() -> None:
    req = Requirement(
        id="REQ-TEST",
        title="Auth",
        description="Desc",
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC-01",
                text="Lock after 5 attempts",
                must_have=[r"5\s*intentos", r"bloqueo"],
            ),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Intento de bloqueo",
            level="negative",
            steps=["Ingresar contraseña errónea durante 5 intentos consecutivos"],
            expected="Mensaje de bloqueo de cuenta",
            covers=["AC-01"],
        ),
    ]
    cov = metrics.verified_coverage([req], {req.id: cases})
    assert cov == 1.0
    assert cov >= 0.70  # Pre-registered threshold


def test_verified_coverage_fail() -> None:
    # Cites criterion AC-01, but steps and expected omit required regex matches
    req = Requirement(
        id="REQ-TEST",
        title="Auth",
        description="Desc",
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC-01",
                text="Lock after 5 attempts",
                must_have=[r"5\s*intentos", r"bloqueo"],
            ),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Prueba genérica sin coincidencia",
            level="functional",
            steps=["Hacer algo en la pantalla"],
            expected="Todo funciona normal",
            covers=["AC-01"],
        ),
    ]
    cov = metrics.verified_coverage([req], {req.id: cases})
    assert cov == 0.0
    assert cov < 0.70  # Fails threshold


def test_hallucinated_refs_pass() -> None:
    req = Requirement(
        id="REQ-TEST",
        title="Cart",
        description="Desc",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Add to cart"),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Test",
            level="smoke",
            steps=["Step 1"],
            expected="OK",
            covers=["AC-01"],
        ),
    ]
    rate = metrics.hallucinated_refs([req], {req.id: cases})
    assert rate == 0.0
    assert rate <= 0.02  # Pre-registered threshold


def test_hallucinated_refs_fail() -> None:
    # Cites non-existent AC-99 -> fails threshold <= 0.02
    req = Requirement(
        id="REQ-TEST",
        title="Cart",
        description="Desc",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-01", text="Add to cart"),
        ],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Hallucinating test case",
            level="functional",
            steps=["Step 1"],
            expected="OK",
            covers=["AC-01", "AC-99-HALLUCINATED"],
        ),
        TestCase(
            id="TC-02",
            title="Valid test case",
            level="smoke",
            steps=["Step 2"],
            expected="OK",
            covers=["AC-01"],
        ),
    ]
    rate = metrics.hallucinated_refs([req], {req.id: cases})
    assert rate == 0.50  # 1 out of 2 cases cites non-existent criteria
    assert rate > 0.02  # Fails threshold


def test_duplicate_rate_pass() -> None:
    req = Requirement(
        id="REQ-TEST",
        title="Search",
        description="Desc",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="Keyword")],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Búsqueda básica por nombre de producto",
            level="smoke",
            steps=["Escribir zapatillas deportivas", "Presionar buscar"],
            expected="Resultados relevantes",
            covers=["AC-01"],
        ),
        TestCase(
            id="TC-02",
            title="Filtrado avanzado por rango de precio",
            level="functional",
            steps=["Seleccionar filtro de precio", "Ajustar deslizador a 50"],
            expected="Artículos filtrados",
            covers=["AC-01"],
        ),
    ]
    rate = metrics.duplicate_rate([req], {req.id: cases})
    assert rate == 0.0
    assert rate <= 0.10  # Pre-registered threshold


def test_duplicate_rate_fail() -> None:
    # Two test cases with identical title and steps -> difflib ratio == 1.0 >= 0.90
    req = Requirement(
        id="REQ-TEST",
        title="Search",
        description="Desc",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="Keyword")],
    )
    cases = [
        TestCase(
            id="TC-01",
            title="Búsqueda básica de zapatos",
            level="smoke",
            steps=["Ingresar texto zapatos", "Presionar Enter"],
            expected="Catálogo actualizado",
            covers=["AC-01"],
        ),
        TestCase(
            id="TC-02",
            title="Búsqueda básica de zapatos",
            level="functional",
            steps=["Ingresar texto zapatos", "Presionar Enter"],
            expected="Catálogo actualizado con ítems",
            covers=["AC-01"],
        ),
    ]
    rate = metrics.duplicate_rate([req], {req.id: cases})
    # 1 duplicate pair / 2 test cases = 0.50
    assert rate == 0.50
    assert rate > 0.10  # Fails threshold


def test_negative_presence_pass() -> None:
    req1 = Requirement(
        id="REQ-01",
        title="Req 1",
        description="Desc",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="T1")],
    )
    req2 = Requirement(
        id="REQ-02",
        title="Req 2",
        description="Desc",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="T2")],
    )
    cases = {
        "REQ-01": [
            TestCase(
                id="TC-01",
                title="Negative test",
                level="negative",
                steps=["Step"],
                expected="Err",
                covers=["AC-01"],
            )
        ],
        "REQ-02": [
            TestCase(
                id="TC-02",
                title="Edge test",
                level="edge",
                steps=["Step"],
                expected="Boundary OK",
                covers=["AC-01"],
            )
        ],
    }
    presence = metrics.negative_presence([req1, req2], cases)
    assert presence == 1.0
    assert presence >= 1.0  # Pre-registered threshold


def test_negative_presence_fail() -> None:
    # Only functional test case, no negative or edge -> 0.0 fails threshold 1.0
    req = Requirement(
        id="REQ-01",
        title="Req 1",
        description="Desc",
        acceptance_criteria=[AcceptanceCriterion(id="AC-01", text="T1")],
    )
    cases = {
        "REQ-01": [
            TestCase(
                id="TC-01",
                title="Happy path only",
                level="functional",
                steps=["Step"],
                expected="OK",
                covers=["AC-01"],
            )
        ]
    }
    presence = metrics.negative_presence([req], cases)
    assert presence == 0.0
    assert presence < 1.0  # Fails threshold
