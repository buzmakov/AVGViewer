from __future__ import annotations

from typing import Any

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import pyqtSignal


def runtime_dh_to_hms(runtime_dh: float) -> str:
    """Convert RunTime_dh decimal hours to HH:MM:SS."""
    total_seconds = int(round((runtime_dh % 24.0) * 3600.0))
    total_seconds %= 24 * 3600
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class PlotCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas with AVG plotting and range selection."""

    selection_changed = pyqtSignal(float, float)
    cursor_changed = pyqtSignal(float, float)

    def __init__(self, parent=None) -> None:
        self.figure = Figure(figsize=(8, 5), constrained_layout=True)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setParent(parent)

        self._avg_df: pd.DataFrame | None = None
        self._display_df: pd.DataFrame | None = None
        self._mph_df: pd.DataFrame | None = None
        self._marks: list[dict[str, Any]] = []
        self._visible_columns: list[str] = []
        self._averaging_seconds = 2
        self._selection_start: float | None = None
        self._selection_end: float | None = None
        self._selection_patch: Rectangle | None = None
        self._dragging = False
        self._current_xlim: tuple[float, float] | None = None
        self._x_zoom_factor = 1.25

        self.mpl_connect("button_press_event", self._on_button_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_button_release)
        self.mpl_connect("scroll_event", self._on_scroll)

    @property
    def selection(self) -> tuple[float, float] | None:
        if self._selection_start is None or self._selection_end is None:
            return None
        start = min(self._selection_start, self._selection_end)
        end = max(self._selection_start, self._selection_end)
        return start, end

    @property
    def display_df(self) -> pd.DataFrame | None:
        """Return the currently displayed physical-values DataFrame after averaging."""
        return self._display_df

    def set_data(
        self,
        avg_df: pd.DataFrame,
        visible_columns: list[str],
        marks: list[dict[str, Any]] | None = None,
    ) -> None:
        self._avg_df = avg_df
        self._visible_columns = visible_columns
        self._marks = marks or []
        self._mph_df = None
        self._selection_start = None
        self._selection_end = None
        self._current_xlim = None
        self.redraw()

    def set_visible_columns(self, visible_columns: list[str]) -> None:
        self._visible_columns = visible_columns
        self.redraw()

    def set_averaging_seconds(self, seconds: int) -> None:
        self._averaging_seconds = max(1, int(seconds))
        self.redraw()

    def set_mph_overlay(self, mph_df: pd.DataFrame | None) -> None:
        self._mph_df = mph_df
        self.redraw()

    def _make_display_df(self) -> pd.DataFrame | None:
        if self._avg_df is None or "RunTime_dh" not in self._avg_df.columns:
            return self._avg_df
        df = self._avg_df.copy()
        if self._averaging_seconds <= 1:
            return df

        seconds_of_day = df["RunTime_dh"] * 3600.0
        bin_index = (seconds_of_day // self._averaging_seconds).astype("int64")
        numeric_columns = df.select_dtypes(include="number").columns.tolist()
        grouped = df[numeric_columns].groupby(bin_index, sort=True).mean(numeric_only=True)
        return grouped.reset_index(drop=True)

    @staticmethod
    def _normalized_series(series: pd.Series) -> pd.Series:
        mean = series.mean(skipna=True)
        std = series.std(skipna=True)
        if pd.isna(std) or std == 0:
            return series * 0.0
        return (series - mean) / std

    def redraw(self) -> None:
        self.axes.clear()
        self._selection_patch = None

        self._display_df = self._make_display_df()
        if self._display_df is None or not self._visible_columns:
            self.axes.set_title("Откройте AVG-файл и выберите серии")
            self.axes.set_xlabel("RunTime_dh")
            self.draw_idle()
            return

        x = self._display_df["RunTime_dh"] if "RunTime_dh" in self._display_df.columns else self._display_df.index
        for column in self._visible_columns:
            if column in self._display_df.columns:
                y = self._normalized_series(self._display_df[column])
                self.axes.plot(x, y, label=column, linewidth=1.2)

        self._draw_marks()
        self._draw_mph_overlay()
        self._draw_selection_patch()

        self.axes.set_xlabel("Время")
        self.axes.set_ylabel("Нормированное отклонение (z-score)")
        self.axes.set_title(f"Сопоставимый масштаб, усреднение {self._averaging_seconds} с")
        self.axes.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: runtime_dh_to_hms(value)))
        self.axes.grid(True, alpha=0.25)
        if self._current_xlim is not None:
            self.axes.set_xlim(*self._current_xlim)
        if self._visible_columns:
            self.axes.legend(loc="best", fontsize="small")
        self.draw_idle()

    def _draw_marks(self) -> None:
        if not self._marks:
            return
        ymin, ymax = self.axes.get_ylim()
        for mark in self._marks:
            runtime = mark.get("runtime_dh")
            if runtime is None:
                continue
            label = str(mark.get("label", ""))
            self.axes.axvline(runtime, color="tab:red", linestyle="--", linewidth=0.8, alpha=0.65)
            self.axes.text(
                runtime,
                ymax,
                label,
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
                color="tab:red",
                alpha=0.8,
            )

    def _draw_mph_overlay(self) -> None:
        if self._mph_df is None or self._mph_df.empty:
            return
        if "RunTime_dh" not in self._mph_df.columns:
            return
        x = self._mph_df["RunTime_dh"]
        for column in self._visible_columns:
            if column in self._mph_df.columns:
                y = self._normalized_series(self._mph_df[column])
                self.axes.plot(x, y, linestyle="none", marker=".", markersize=2, alpha=0.55)

    def _draw_selection_patch(self) -> None:
        selected = self.selection
        if selected is None:
            return
        x0, x1 = selected
        ymin, ymax = self.axes.get_ylim()
        self._selection_patch = Rectangle(
            (x0, ymin),
            x1 - x0,
            ymax - ymin,
            facecolor="tab:green",
            alpha=0.15,
            edgecolor="tab:green",
        )
        self.axes.add_patch(self._selection_patch)

    def _on_button_press(self, event) -> None:
        if event.button != 1 or event.inaxes != self.axes or event.xdata is None:
            return
        self._dragging = True
        self._selection_start = float(event.xdata)
        self._selection_end = float(event.xdata)
        self.redraw()

    def _on_scroll(self, event) -> None:
        if event.inaxes != self.axes or event.xdata is None:
            return

        left, right = self.axes.get_xlim()
        width = right - left
        if width <= 0:
            return

        cursor_x = float(event.xdata)
        zoom_factor = self._x_zoom_factor if event.button == "up" else 1.0 / self._x_zoom_factor
        new_width = width / zoom_factor

        left_fraction = (cursor_x - left) / width
        right_fraction = (right - cursor_x) / width
        new_left = cursor_x - new_width * left_fraction
        new_right = cursor_x + new_width * right_fraction

        self._current_xlim = (new_left, new_right)
        self.axes.set_xlim(new_left, new_right)
        self.draw_idle()

    def _on_motion(self, event) -> None:
        if event.inaxes == self.axes and event.xdata is not None and event.ydata is not None:
            self.cursor_changed.emit(float(event.xdata), float(event.ydata))
        if not self._dragging or event.inaxes != self.axes or event.xdata is None:
            return
        self._selection_end = float(event.xdata)
        self.redraw()

    def _on_button_release(self, event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        if event.inaxes == self.axes and event.xdata is not None:
            self._selection_end = float(event.xdata)
        selected = self.selection
        if selected is not None and abs(selected[1] - selected[0]) > 1e-9:
            self.selection_changed.emit(selected[0], selected[1])
        self.redraw()
