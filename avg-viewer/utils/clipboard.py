from __future__ import annotations

import pandas as pd
from PyQt6.QtWidgets import QApplication


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
    columns = ["RunTime_dh"] + [column for column in visible_columns if column in df.columns]
    selected = df.loc[(df["RunTime_dh"] >= start) & (df["RunTime_dh"] <= end), columns]
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
