from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ChannelPanel(QWidget):
    """Panel with channel visibility checkboxes."""

    channels_changed = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        buttons_layout = QHBoxLayout()
        self.select_all_button = QPushButton("Все")
        self.clear_button = QPushButton("Снять")
        self.select_all_button.clicked.connect(self.select_all)
        self.clear_button.clicked.connect(self.clear_all)
        buttons_layout.addWidget(self.select_all_button)
        buttons_layout.addWidget(self.clear_button)
        main_layout.addLayout(buttons_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.channels_widget = QWidget()
        self.channels_layout = QVBoxLayout(self.channels_widget)
        self.channels_layout.addStretch(1)
        self.scroll_area.setWidget(self.channels_widget)
        main_layout.addWidget(self.scroll_area)

    def set_channels(self, channels: list[str], checked: list[str] | None = None) -> None:
        checked_set = set(checked or channels[:3])
        while self.channels_layout.count() > 1:
            item = self.channels_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._checkboxes.clear()
        for channel in channels:
            checkbox = QCheckBox(channel)
            checkbox.setChecked(channel in checked_set)
            checkbox.stateChanged.connect(self._emit_channels_changed)
            self.channels_layout.insertWidget(self.channels_layout.count() - 1, checkbox)
            self._checkboxes[channel] = checkbox

        self._emit_channels_changed()

    def selected_channels(self) -> list[str]:
        return [channel for channel, checkbox in self._checkboxes.items() if checkbox.isChecked()]

    def select_all(self) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(True)
        self._emit_channels_changed()

    def clear_all(self) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(False)
        self._emit_channels_changed()

    def _emit_channels_changed(self) -> None:
        self.channels_changed.emit(self.selected_channels())
