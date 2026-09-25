# T08 — Entrada en Excel (.xlsx) y JSON además de CSV (proyecto 04)

**Objetivo:** un único lector `read_table(data, filename)` que elige el parser por extensión.
Lo usan `/clean` (síncrono y asíncrono) y las tareas Celery.
- Extensión no soportada → **415**.
- Archivo ilegible → **400**.

**Archivos que puedes tocar:**
- `04-data-cleaning-api/app/services/readers.py` (nuevo)
- `04-data-cleaning-api/app/api/routes/clean.py`
- `04-data-cleaning-api/app/services/tasks.py`
- `04-data-cleaning-api/tests/test_api.py`

## Antes de empezar

- `T07` en `DONE`. Compuertas → **41 passed, 3 deselected**.
- `Select-String -Path requirements.txt -Pattern "openpyxl"` → 1 coincidencia (ya instalado).

## Paso 1 — `app/services/readers.py` (nuevo)

EXACTO:

```python
"""Parse uploaded bytes into a DataFrame based on the file extension."""

import io
import zipfile

import pandas as pd

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".json")

# Errors that mean "the file content is bad" -> HTTP 400.
PARSE_ERRORS: tuple[type[Exception], ...] = (
    pd.errors.EmptyDataError,
    pd.errors.ParserError,
    UnicodeDecodeError,
    ValueError,
    zipfile.BadZipFile,
)


class UnsupportedFormatError(Exception):
    """The file extension is not one of SUPPORTED_EXTENSIONS."""


def is_supported(filename: str | None) -> bool:
    return filename is not None and filename.lower().endswith(SUPPORTED_EXTENSIONS)


def read_table(data: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(data))
    if name.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(data), engine="openpyxl")
    if name.endswith(".json"):
        return pd.read_json(io.BytesIO(data), orient="records")
    raise UnsupportedFormatError(filename)
```

## Paso 2 — `app/api/routes/clean.py`

2a. Borra la línea `import io`.

2b. Borra la línea
`PARSE_ERRORS = (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError)`.

2c. Agrega el import (ruff lo ordena):
`from app.services.readers import PARSE_ERRORS, SUPPORTED_EXTENSIONS, is_supported, read_table`

2d. Si después de 2a–2c ya nada usa `pd` en el archivo, borra `import pandas as pd`
(ruff `F401` te lo dirá).

2e. Inmediatamente **después** de `file_bytes = await file.read()` inserta. EXACTO
(4 espacios de sangría):

```python
    filename = file.filename or ""
    if not is_supported(filename):
        raise HTTPException(415, f"Unsupported file type. Use one of: {SUPPORTED_EXTENSIONS}")
```

2f. En la rama síncrona reemplaza `df = pd.read_csv(io.BytesIO(file_bytes))` por
`df = read_table(file_bytes, filename)`. El `except PARSE_ERRORS as e:` que ya existe se queda
igual (ahora usa la tupla importada).

2g. En la rama asíncrona reemplaza `f"raw_{job_id}_{file.filename}"` por
`f"raw_{job_id}_{filename}"`.

## Paso 3 — `app/services/tasks.py`

3a. Reemplaza la función `_load` completa por. EXACTO:

```python
def _load(file_path: str) -> pd.DataFrame:
    return read_table(download_file(file_path), file_path)
```

3b. Agrega el import `from .readers import read_table` junto a los demás imports relativos.
3c. Si `io` sigue usándose (sí: `io.BytesIO()` en `_run`), no lo borres.

## Paso 4 — `tests/test_api.py`

Agrega `import pandas as pd` a los imports. Al final del archivo agrega. EXACTO:

```python


def test_clean_accepts_xlsx():
    buf = io.BytesIO()
    pd.DataFrame({"A": [1, 1, 2]}).to_excel(buf, index=False)
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.xlsx", io.BytesIO(buf.getvalue()))},
        data={"options": '{"remove_duplicates": true}'},
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2


def test_clean_accepts_json_records():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.json", io.BytesIO(b'[{"A": 1}, {"A": 1}, {"A": 2}]'))},
        data={"options": '{"remove_duplicates": true}'},
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2


def test_clean_rejects_unsupported_extension():
    res = client.post(
        "/api/v1/clean",
        files={"file": ("t.txt", io.BytesIO(b"A\n1\n"))},
        data={"options": "{}"},
    )
    assert res.status_code == 415
```

## Verificación

1. Compuertas → **44 passed, 3 deselected**, ruff y mypy limpios.
2. `Select-String -Path app -Recurse -Pattern "read_csv"` → **1** coincidencia, en
   `app\services\readers.py`.

## Terminado cuando

Ambas pasan. Reporta y marca `T08` como `DONE`.
