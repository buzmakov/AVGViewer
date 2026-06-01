from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .parser import parse_avg, parse_config, parse_marks, parse_min, parse_mph, visible_avg_columns


@dataclass
class ExperimentSeries:
    """Represents one experiment series built around an AVG file."""

    avg_path: Path
    _avg_df: pd.DataFrame | None = field(default=None, init=False, repr=False)
    _mph_df: pd.DataFrame | None = field(default=None, init=False, repr=False)
    _min_df: pd.DataFrame | None = field(default=None, init=False, repr=False)
    _marks: list[dict[str, Any]] | None = field(default=None, init=False, repr=False)
    _config: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.avg_path = Path(self.avg_path)
        if not self.avg_path.exists():
            raise FileNotFoundError(f"AVG file not found: {self.avg_path}")

    @property
    def directory(self) -> Path:
        return self.avg_path.parent

    @property
    def avg_stem(self) -> str:
        return self.avg_path.stem

    @property
    def base_prefix(self) -> str:
        suffix = "_001"
        stem = self.avg_stem
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
        return stem

    @property
    def name(self) -> str:
        return self.base_prefix

    @property
    def mph_path(self) -> Path:
        return self.directory / f"{self.base_prefix}_001.MPH"

    @property
    def min_path(self) -> Path:
        return self.directory / f"{self.base_prefix}.MIN"

    @property
    def marks_path(self) -> Path:
        return self.directory / f"{self.base_prefix}_Marks.txt"

    @property
    def config_info_path(self) -> Path:
        return self.directory / f"{self.base_prefix}_Config_Info.txt"

    @property
    def avg_lv_path(self) -> Path:
        return self.directory / f"{self.base_prefix}_AVG-LV_001"

    @property
    def available_files(self) -> dict[str, Path]:
        candidates = {
            "avg": self.avg_path,
            "mph": self.mph_path,
            "min": self.min_path,
            "marks": self.marks_path,
            "config_info": self.config_info_path,
            "avg_lv": self.avg_lv_path,
        }
        return {key: path for key, path in candidates.items() if path.exists()}

    def load_avg(self) -> pd.DataFrame:
        if self._avg_df is None:
            self._avg_df = parse_avg(self.avg_path)
        return self._avg_df

    def load_mph(self) -> pd.DataFrame:
        if self._mph_df is None:
            if not self.mph_path.exists():
                raise FileNotFoundError(f"MPH file not found: {self.mph_path}")
            self._mph_df = parse_mph(self.mph_path)
        return self._mph_df

    def load_min(self) -> pd.DataFrame:
        if self._min_df is None:
            if not self.min_path.exists():
                raise FileNotFoundError(f"MIN file not found: {self.min_path}")
            self._min_df = parse_min(self.min_path)
        return self._min_df

    def load_marks(self) -> list[dict[str, Any]]:
        if self._marks is None:
            self._marks = parse_marks(self.marks_path)
        return self._marks

    def load_config(self) -> dict[str, Any]:
        if self._config is None:
            self._config = parse_config(self.config_info_path)
        return self._config

    def visible_columns(self) -> list[str]:
        return visible_avg_columns(self.load_avg())
