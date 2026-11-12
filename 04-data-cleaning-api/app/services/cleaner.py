import logging

import pandas as pd

logger = logging.getLogger(__name__)


def clean_dataframe(df: pd.DataFrame, options: dict) -> pd.DataFrame:
    """
    Cleans a pandas DataFrame based on the provided options.

    Args:
        df (pd.DataFrame): The DataFrame to clean.
        options (dict): Dictionary containing cleaning options.

    Returns:
        pd.DataFrame: The cleaned DataFrame.
    """
    logger.info("Starting DataFrame cleaning process")
    cleaned_df = df.copy()

    try:
        if options.get("remove_empty_rows", True):
            cleaned_df.dropna(how="all", inplace=True)

        if options.get("remove_empty_cols", True):
            cleaned_df.dropna(axis=1, how="all", inplace=True)

        if options.get("remove_duplicates", False):
            cleaned_df.drop_duplicates(inplace=True)

        handle_nulls = options.get("handle_nulls")
        if handle_nulls == "drop":
            cleaned_df.dropna(inplace=True)
        elif handle_nulls == "fill_value":
            fill_val = options.get("null_fill_value", "Unknown")
            cleaned_df.fillna(fill_val, inplace=True)
        elif handle_nulls == "interpolate":
            numeric_cols = cleaned_df.select_dtypes(include=["number"]).columns
            cleaned_df[numeric_cols] = cleaned_df[numeric_cols].interpolate()
            cleaned_df.bfill(inplace=True)
            cleaned_df.ffill(inplace=True)

        str_cols = cleaned_df.select_dtypes(include=["object", "string"]).columns

        if options.get("trim_whitespace", True):
            for col in str_cols:
                cleaned_df[col] = cleaned_df[col].astype(str).str.strip()

        if options.get("normalize_lowercase", False):
            for col in str_cols:
                cleaned_df[col] = cleaned_df[col].astype(str).str.lower()

        cleaned_df = cleaned_df.convert_dtypes()

    except Exception as e:
        logger.error(f"Error during DataFrame cleaning: {str(e)}")
        raise

    return cleaned_df
