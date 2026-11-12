import logging

import pandas as pd

logger = logging.getLogger(__name__)


def pivot_data(df: pd.DataFrame, index: str, columns: str, values: str) -> pd.DataFrame:
    return df.pivot(index=index, columns=columns, values=values).reset_index()


def melt_data(df: pd.DataFrame, id_vars: list, value_vars: list) -> pd.DataFrame:
    return pd.melt(df, id_vars=id_vars, value_vars=value_vars)


def merge_columns(df: pd.DataFrame, columns: list, separator: str, new_name: str) -> pd.DataFrame:
    df_merged = df.copy()
    df_merged[new_name] = df_merged[columns].astype(str).agg(separator.join, axis=1)
    return df_merged


def split_column(df: pd.DataFrame, column: str, separator: str, new_names: list) -> pd.DataFrame:
    df_split = df.copy()
    df_split[new_names] = (
        df_split[column].astype(str).str.split(separator, expand=True, n=len(new_names) - 1)
    )
    return df_split


def aggregate_data(
    df: pd.DataFrame, group_by: list, agg_column: str, agg_func: str
) -> pd.DataFrame:
    return df.groupby(group_by)[agg_column].agg(agg_func).reset_index()
