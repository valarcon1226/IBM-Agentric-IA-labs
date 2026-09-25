import numpy as np
import pandas as pd

from app.services.cleaner import clean_dataframe


def test_remove_duplicates():
    df = pd.DataFrame({"A": [1, 2, 2], "B": ["a", "b", "b"]})
    res = clean_dataframe(df, {"remove_duplicates": True})
    assert len(res) == 2


def test_fill_na_interpolate():
    df = pd.DataFrame({"A": [1.0, np.nan, 3.0]})
    res = clean_dataframe(df, {"handle_nulls": "interpolate"})
    assert res["A"].isnull().sum() == 0


def test_trim_whitespace():
    df = pd.DataFrame({"A": [" a "]})
    res = clean_dataframe(df, {"trim_whitespace": True})
    assert res["A"][0] == "a"


def test_remove_empty_rows():
    df = pd.DataFrame({"A": [1, np.nan], "B": ["a", np.nan]})
    res = clean_dataframe(df, {"remove_empty_rows": True})
    assert len(res) == 1
