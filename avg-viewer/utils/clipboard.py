from __future__ import annotations

import pandas as pd
from PyQt6.QtWidgets import QApplication


def _runtime_dh_to_hms(runtime_dh: float) -> str:
    """Convert RunTime_dh decimal hours to HH:MM:SS for clipboard export."""
    total_seconds = int(round((runtime_dh % 24.0) * 3600.0))
    total_seconds %= 24 * 3600
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def average_dataframe_by_runtime(df: pd.DataFrame, seconds: int) -> pd.DataFrame:
    """Return a runtime-binned copy of numeric values for clipboard export."""
    if seconds <= 1 or "RunTime_dh" not in df.columns:
        return df.copy()

    seconds_of_day = df["RunTime_dh"] * 3600.0
    bin_index = (seconds_of_day // seconds).astype("int64")
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    grouped = df[numeric_columns].groupby(bin_index, sort=True).mean(numeric_only=True)
    return grouped.reset_index(drop=True)


def dataframe_selection_to_tsv(
    df: pd.DataFrame,
    visible_columns: list[str],
    start_dh: float,
    end_dh: float,
) -> str:
    """Return selected visible AVG values as TSV text."""
    if "RunTime_dh" not in df.columns:
        return ""

    start, end = sorted((start_dh, end_dh))
    value_columns = [column for column in visible_columns if column in df.columns]
    columns = ["RunTime_dh"] + value_columns
    selected = df.loc[(df["RunTime_dh"] >= start) & (df["RunTime_dh"] <= end), columns].copy()
    selected.insert(0, "Time", selected["RunTime_dh"].map(_runtime_dh_to_hms))
    selected = selected.drop(columns=["RunTime_dh"])
    return selected.to_csv(sep="\t", index=False, float_format="%.9g")


def copy_selection_to_clipboard(
    df: pd.DataFrame,
    visible_columns: list[str],
    start_dh: float,
    end_dh: float,
) -> int:
    """Copy selected visible AVG values to the system clipboard and return row count."""
    tsv = dataframe_selection_to_tsv(df, visible_columns, start_dh, end_dh)
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(tsv)
    if not tsv.strip():
        return 0
    return max(0, len(tsv.splitlines()) - 1)
