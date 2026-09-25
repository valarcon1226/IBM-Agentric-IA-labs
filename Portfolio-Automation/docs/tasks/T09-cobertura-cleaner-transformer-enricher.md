# T09 — Tests para cleaner, transformer y enricher (proyecto 04)

**Objetivo:** cubrir las opciones de limpieza sin tests y todas las funciones de
transformación y enriquecimiento (escenarios DC-CLEAN-005, DC-TRF-001, DC-ENR-001).
**No se toca código de `app/`.** Estos tests ya se ejecutaron contra el código actual y pasan.

**Archivos que puedes tocar:** `04-data-cleaning-api/tests/test_transformations.py` (nuevo).

## Antes de empezar

- `T08` en `DONE`. Compuertas → **44 passed, 3 deselected**.

## Paso 1 — `tests/test_transformations.py` (nuevo)

EXACTO:

```python
import numpy as np
import pandas as pd

from app.services.cleaner import clean_dataframe
from app.services.enricher import normalize_phones, validate_emails
from app.services.transformer import (
    aggregate_data,
    melt_data,
    merge_columns,
    pivot_data,
    split_column,
)


def test_handle_nulls_drop_removes_incomplete_rows():
    df = pd.DataFrame({"A": [1.0, np.nan, 3.0], "B": ["x", "y", "z"]})
    res = clean_dataframe(df, {"handle_nulls": "drop"})
    assert len(res) == 2


def test_handle_nulls_fill_value_uses_given_value():
    df = pd.DataFrame({"A": [1, 2], "B": ["x", None]})
    res = clean_dataframe(df, {"handle_nulls": "fill_value", "null_fill_value": "n/a"})
    assert list(res["B"]) == ["x", "n/a"]


def test_pivot_data():
    df = pd.DataFrame({"date": ["d1", "d1", "d2"], "cat": ["a", "b", "a"], "rev": [10, 20, 30]})
    res = pivot_data(df, index="date", columns="cat", values="rev")
    assert list(res.columns) == ["date", "a", "b"]
    assert res.loc[res["date"] == "d1", "b"].item() == 20


def test_melt_data():
    df = pd.DataFrame({"id": [1], "x": [5], "y": [6]})
    res = melt_data(df, id_vars=["id"], value_vars=["x", "y"])
    assert list(res.columns) == ["id", "variable", "value"]
    assert len(res) == 2


def test_merge_columns():
    df = pd.DataFrame({"first": ["Ana"], "last": ["Paz"]})
    res = merge_columns(df, columns=["first", "last"], separator=" ", new_name="full")
    assert res["full"].item() == "Ana Paz"


def test_split_column():
    df = pd.DataFrame({"full": ["Ana Paz"]})
    res = split_column(df, column="full", separator=" ", new_names=["first", "last"])
    assert (res["first"].item(), res["last"].item()) == ("Ana", "Paz")


def test_aggregate_data():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 5]})
    res = aggregate_data(df, group_by=["g"], agg_column="v", agg_func="sum")
    assert dict(zip(res["g"], res["v"], strict=True)) == {"a": 3, "b": 5}


def test_validate_emails_flags_invalid_and_missing():
    df = pd.DataFrame({"email": ["ana@example.com", "not-an-email", None]})
    res = validate_emails(df, "email")
    assert list(res["email_valid"]) == [True, False, False]


def test_normalize_phones_formats_valid_and_flags_invalid():
    df = pd.DataFrame({"phone": ["(202) 555-0143", "123"]})
    res = normalize_phones(df, "phone")
    assert list(res["phone_e164"]) == ["+12025550143", "123"]
    assert list(res["phone_valid"]) == [True, False]
```

Si un test falla: **no cambies el test ni el código de `app/`**. Detente y reporta la salida
completa. Un fallo aquí significa que el comportamiento de `app/` cambió en T01–T08.

## Verificación

1. Compuertas → **53 passed, 3 deselected**, ruff y mypy limpios.
2. La cobertura total es **mayor** que la del reporte de T08.

## Terminado cuando

Ambas pasan. Reporta y marca `T09` como `DONE`.
