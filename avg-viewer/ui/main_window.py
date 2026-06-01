from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from data.series import ExperimentSeries
from ui.channel_panel import ChannelPanel
from ui.plot_canvas import PlotCanvas, runtime_dh_to_hms
from utils.clipboard import average_dataframe_by_runtime, copy_selection_to_clipboard


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AVG Viewer")
        self.resize(1200, 800)

        self.settings = QSettings("AVGViewer", "AVGViewer")
        self.series: ExperimentSeries | None = None
        self.selection: tuple[float, float] | None = None
        self._updating_time_scroll = False

        self._build_ui()
        self._build_menu()
        self._update_actions()

    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QVBoxLayout(central)

        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        splitter = QSplitter()
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.channel_panel = ChannelPanel()
        self.channel_panel.setMinimumWidth(220)
        self.channel_panel.channels_changed.connect(self._on_channels_changed)
        left_layout.addWidget(self.channel_panel, 1)

        left_layout.addWidget(QLabel("Метки:"))
        self.marks_list = QListWidget()
        self.marks_list.setMinimumHeight(140)
        self.marks_list.itemClicked.connect(self._jump_to_mark)
        self.marks_list.itemActivated.connect(self._jump_to_mark)
        left_layout.addWidget(self.marks_list, 0)

        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(2)
        self.plot_canvas = PlotCanvas()
        self.plot_canvas.selection_changed.connect(self._on_selection_changed)
        self.plot_canvas.cursor_changed.connect(self._on_cursor_changed)
        self.plot_canvas.x_limits_changed.connect(self._on_x_limits_changed)
        self.toolbar = NavigationToolbar2QT(self.plot_canvas, self)
        self.time_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.time_scroll.setRange(0, 10000)
        self.time_scroll.setEnabled(False)
        self.time_scroll.valueChanged.connect(self._on_time_scroll_changed)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.plot_canvas)
        plot_layout.addWidget(self.time_scroll)

        splitter.addWidget(left_container)
        splitter.addWidget(plot_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        buttons_layout = QHBoxLayout()
        self.averaging_combo = QComboBox()
        for seconds in (1, 2, 5, 10, 60):
            self.averaging_combo.addItem(f"{seconds} с", seconds)
        self.averaging_combo.setCurrentIndex(1)
        self.averaging_combo.currentIndexChanged.connect(self._on_averaging_changed)
        self.copy_button = QPushButton("Copy selection TSV (Ctrl+C)")
        self.copy_button.clicked.connect(self._copy_selection)
        self.mph_button = QPushButton("Показать MPH в выделении")
        self.mph_button.clicked.connect(self._toggle_mph_for_selection)
        buttons_layout.addWidget(QLabel("Усреднение для копирования:"))
        buttons_layout.addWidget(self.averaging_combo)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.mph_button)
        buttons_layout.addWidget(self.copy_button)
        main_layout.addLayout(buttons_layout)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Готово")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_action = file_menu.addAction("Open AVG...")
        open_action.triggered.connect(self.open_avg_dialog)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Exit")
        quit_action.triggered.connect(self.close)

        self.copy_action = QAction("Copy selection TSV", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self._copy_selection)
        self.addAction(self.copy_action)

    def open_avg_dialog(self) -> None:
        last_dir = self.settings.value("last_dir", str(Path.cwd()), str)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open AVG file",
            last_dir,
            "AVG files (*.AVG);;All files (*.*)",
        )
        if filename:
            self.settings.setValue("last_dir", str(Path(filename).parent))
            self.open_avg(Path(filename))

    def open_avg(self, path: Path) -> None:
        try:
            self.series = ExperimentSeries(path)
            avg_df = self.series.load_avg()
            marks = self.series.load_marks()
            visible_columns = self.series.visible_columns()
            default_columns = [column for column in ["HR, bpm", "Mean BP", "Syst BP", "Diast BP"] if column in visible_columns]
            self.channel_panel.set_channels(visible_columns, checked=default_columns or visible_columns[:3])
            self.plot_canvas.set_data(avg_df, self.channel_panel.selected_channels(), marks)
            self._populate_marks(marks)
            self.selection = None
            self.statusBar().showMessage(
                f"{self.series.name} — AVG rows: {len(avg_df)}, Marks: {len(marks)}, "
                f"Files: {', '.join(self.series.available_files)}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка открытия файла", str(exc))
        finally:
            self._update_actions()

    def _populate_marks(self, marks: list[dict[str, Any]]) -> None:
        self.marks_list.clear()
        for mark in marks:
            runtime = mark.get("runtime_dh")
            if runtime is None:
                continue
            label = str(mark.get("label", ""))
            index = mark.get("index", "")
            item = QListWidgetItem(f"{index}. {runtime_dh_to_hms(float(runtime))} — {label}")
            item.setData(Qt.ItemDataRole.UserRole, float(runtime))
            self.marks_list.addItem(item)

    def _jump_to_mark(self, item: QListWidgetItem) -> None:
        runtime = item.data(Qt.ItemDataRole.UserRole)
        if runtime is None:
            return
        self.plot_canvas.center_on_time(float(runtime))
        self.statusBar().showMessage(f"Переход к метке: {runtime_dh_to_hms(float(runtime))}")

    def _on_channels_changed(self, channels: list[str]) -> None:
        self.plot_canvas.set_visible_columns(channels)
        self._update_actions()

    def _on_averaging_changed(self) -> None:
        self.statusBar().showMessage(
            f"Усреднение при копировании: {int(self.averaging_combo.currentData())} с"
        )

    def _on_selection_changed(self, start_dh: float, end_dh: float) -> None:
        self.selection = (start_dh, end_dh)
        self.statusBar().showMessage(
            f"Выделено: {runtime_dh_to_hms(start_dh)} — {runtime_dh_to_hms(end_dh)}"
        )
        self._update_actions()

    def _on_cursor_changed(self, x: float, y: float) -> None:
        self.statusBar().showMessage(f"t={runtime_dh_to_hms(x)}, y={y:.4g}")

    def _on_x_limits_changed(self, full_left: float, full_right: float, view_left: float, view_right: float) -> None:
        full_width = full_right - full_left
        view_width = view_right - view_left
        enabled = full_width > 0 and view_width > 0 and view_width < full_width
        self._updating_time_scroll = True
        try:
            self.time_scroll.setEnabled(enabled)
            if not enabled:
                self.time_scroll.setValue(0)
                return
            page_step = max(1, min(10000, round(10000 * view_width / full_width)))
            max_value = max(0, 10000 - page_step)
            value = round(max_value * (view_left - full_left) / (full_width - view_width))
            self.time_scroll.setPageStep(page_step)
            self.time_scroll.setSingleStep(max(1, page_step // 10))
            self.time_scroll.setRange(0, max_value)
            self.time_scroll.setValue(max(0, min(max_value, value)))
        finally:
            self._updating_time_scroll = False

    def _on_time_scroll_changed(self, value: int) -> None:
        if self._updating_time_scroll:
            return
        maximum = self.time_scroll.maximum()
        fraction = 0.0 if maximum <= 0 else value / maximum
        self.plot_canvas.set_time_window_start_fraction(fraction)

    def _copy_selection(self) -> None:
        if self.series is None or self.selection is None:
            return
        try:
            start, end = self.selection
            source_df = average_dataframe_by_runtime(
                self.series.load_avg(),
                int(self.averaging_combo.currentData()),
            )
            row_count = copy_selection_to_clipboard(
                source_df,
                self.channel_panel.selected_channels(),
                start,
                end,
            )
            self.statusBar().showMessage(f"Скопировано строк: {row_count}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка копирования", str(exc))

    def _toggle_mph_for_selection(self) -> None:
        if self.series is None or self.selection is None:
            return
        if self.plot_canvas.mph_overlay_visible:
            self.plot_canvas.clear_mph_overlay()
            self.mph_button.setText("Показать MPH в выделении")
            self.statusBar().showMessage("MPH скрыт")
            return
        try:
            start, end = self.selection
            mph_df = self.series.load_mph()
            if "RunTime_dh" in mph_df.columns:
                mph_df = mph_df[(mph_df["RunTime_dh"] >= start) & (mph_df["RunTime_dh"] <= end)]
            self.plot_canvas.set_mph_overlay(mph_df)
            self.mph_button.setText("Скрыть MPH")
            self.statusBar().showMessage(f"MPH-точек в выделении: {len(mph_df)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка загрузки MPH", str(exc))

    def _update_actions(self) -> None:
        has_selection = self.series is not None and self.selection is not None
        can_copy = has_selection and bool(self.channel_panel.selected_channels())
        self.copy_button.setEnabled(can_copy)
        if hasattr(self, "copy_action"):
            self.copy_action.setEnabled(can_copy)
        self.mph_button.setEnabled(has_selection and self.series is not None and self.series.mph_path.exists())
        if not self.plot_canvas.mph_overlay_visible:
            self.mph_button.setText("Показать MPH в выделении")
