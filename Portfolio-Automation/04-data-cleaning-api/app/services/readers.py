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
