from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


AVG_SKIP_ROWS = 7
MPH_SKIP_ROWS = 7

AVG_SERVICE_COLUMNS = {"Counts", "RunTime_s", "RunTime_dh", "BIN Offset"}
MPH_SERVICE_COLUMNS = {"Syst time (ms)", "RunTime_dh", "BIN Offset"}


def _read_text_table(path: Path, *, skiprows: int) -> pd.DataFrame:
    """Read a tab-separated LabVIEW text table with decimal comma.

    Some rows contain an embedded mark text after the last numeric field.
    The header defines the expected table width, so extra trailing fields are ignored.
    """
    with path.open("r", encoding="cp1251", errors="replace") as file:
        for _ in range(skiprows):
            next(file)
        header = next(file).rstrip("\r\n")

    columns = [column.strip() for column in header.split("\t")]
    df = pd.read_csv(
        path,
        sep="\t",
        skiprows=skiprows + 1,
        header=None,
        names=columns,
        usecols=list(range(len(columns))),
        decimal=",",
        na_values=["NaN", "nan", ""],
        engine="python",
        encoding="cp1251",
    )
    df.columns = [str(column).strip() for column in df.columns]
    df = df.dropna(axis=1, how="all")
    return df


def parse_avg(path: str | Path) -> pd.DataFrame:
    """Parse an AVG file with 2-second averaged values."""
    return _read_text_table(Path(path), skiprows=AVG_SKIP_ROWS)


def parse_mph(path: str | Path) -> pd.DataFrame:
    """Parse an MPH file with beat-by-beat values."""
    return _read_text_table(Path(path), skiprows=MPH_SKIP_ROWS)


def parse_min(path: str | Path) -> pd.DataFrame:
    """Parse a MIN file with minute-averaged values."""
    columns = [
        "Index",
        "RunTime_dh",
        "HR, bpm",
        "Mean BP",
        "Syst BP",
        "Diast BP",
        "Max_dBP/dT",
        "Syst LVP",
        "Diast LVP",
        "EDP",
        "Max_dLVP",
        "Min_dLVP",
        "Max_dLVP/P",
        "Min_dLVP/P",
        "DvP",
        "ICF",
        "BIN Offset",
    ]
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=columns,
        usecols=list(range(len(columns))),
        decimal=",",
        na_values=["NaN", "nan", ""],
        engine="python",
        encoding="cp1251",
    )
    return df.dropna(axis=1, how="all")


_MARK_RE = re.compile(
    r"^\s*(?P<index>\d+)\s*"
    r"-\s*(?P<time>\d{2}:\d{2}:\d{2})\s*"
    r"-\s*Day\s*(?P<day>\d+)\s*"
    r"-\s*(?P<date>\d{4}-\d{2}-\d{2})\s*"
    r"-\s*(?P<label>.*?)\s+"
    r"(?P<minutes>-?\d+(?:,\d+)?)\s+"
    r"(?P<runtime_dh>-?\d+(?:,\d+)?)\s+"
    r"(?P<day_fraction>-?\d+(?:,\d+)?)\s*$"
)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def parse_marks(path: str | Path) -> list[dict[str, Any]]:
    """Parse a Marks.txt file into dictionaries."""
    marks: list[dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return marks

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        match = _MARK_RE.match(line)
        if match is None:
            continue
        data = match.groupdict()
        marks.append(
            {
                "index": int(data["index"]),
                "time": data["time"],
                "day": int(data["day"]),
                "date": data["date"],
                "label": data["label"].strip(),
                "minutes": _to_float(data["minutes"]),
                "runtime_dh": _to_float(data["runtime_dh"]),
                "day_fraction": _to_float(data["day_fraction"]),
            }
        )
    return marks


def parse_config(path: str | Path) -> dict[str, Any]:
    """Parse basic configuration values from Config_Info.txt."""
    path = Path(path)
    config: dict[str, Any] = {"channels": []}
    if not path.exists():
        return config

    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Exp Name:"):
            config["exp_name"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Start Time:"):
            config["start_time"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("First Name:"):
            config["first_name"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Project:"):
            config["project"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Sampling Frequency"):
            match = re.search(r"(-?\d+(?:,\d+)?)", stripped)
            if match:
                config["sampling_frequency_hz"] = _to_float(match.group(1))
        elif stripped.startswith("Averaging Time"):
            match = re.search(r"(-?\d+(?:,\d+)?)", stripped)
            if match:
                config["averaging_time_s"] = _to_float(match.group(1))
        elif stripped.startswith("Channel:"):
            channel_match = re.match(
                r"Channel:\s*(?P<index>\d+)\s+"
                r"(?P<v_lo>-?\d+,?\d*)\s*-\s*(?P<v_hi>-?\d+,?\d*)\s+"
                r"(?P<val_lo>-?\d+,?\d*)\s*-\s*(?P<val_hi>-?\d+,?\d*)\s+"
                r"(?P<decimals>\d+)\s+(?P<name>\S+)",
                stripped,
            )
            if channel_match:
                channel = channel_match.groupdict()
                config["channels"].append(
                    {
                        "index": int(channel["index"]),
                        "voltage_low": _to_float(channel["v_lo"]),
                        "voltage_high": _to_float(channel["v_hi"]),
                        "value_low": _to_float(channel["val_lo"]),
                        "value_high": _to_float(channel["val_hi"]),
                        "decimals": int(channel["decimals"]),
                        "name": channel["name"],
                    }
                )
    return config


def visible_avg_columns(df: pd.DataFrame) -> list[str]:
    """Return data columns suitable for plotting from an AVG-like DataFrame."""
    return [column for column in df.columns if column not in AVG_SERVICE_COLUMNS]
