"""Reusable Qt widgets shared by Packrat's pages."""

from __future__ import annotations

import os
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class FolderListEditor(QWidget):
    """A list of folders with add/remove buttons, Déjà Dup style."""

    changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget(self)
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list)
        buttons = QHBoxLayout()
        self._add_button = QPushButton("Add Folder…")
        self._add_button.clicked.connect(self._on_add)
        self._remove_button = QPushButton("Remove")
        self._remove_button.clicked.connect(self._on_remove)
        self._remove_button.setEnabled(False)
        self._list.itemSelectionChanged.connect(
            lambda: self._remove_button.setEnabled(bool(self._list.selectedItems()))
        )
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def folders(self) -> List[str]:
        result: List[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None:
                result.append(item.text())
        return result

    def set_folders(self, folders: List[str]) -> None:
        self._list.clear()
        for folder in folders:
            QListWidgetItem(folder, self._list)

    def _on_add(self) -> None:
        start = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Choose a folder to back up", start)
        if directory:
            if directory not in self.folders():
                QListWidgetItem(directory, self._list)
            self.changed.emit()

    def _on_remove(self) -> None:
        for item in list(self._list.selectedItems()):
            self._list.takeItem(self._list.row(item))
        self.changed.emit()


class StatusBadge(QLabel):
    """Small coloured status pill used on the overview page."""

    _STYLES = {
        "ok": "background-color: #2ebd59; color: white;",
        "warn": "background-color: #e6a123; color: white;",
        "error": "background-color: #d9534f; color: white;",
        "idle": "background-color: #6c757d; color: white;",
        "info": "background-color: #3178c6; color: white;",
    }

    def __init__(
        self, text: str = "", state: str = "idle", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        style = self._STYLES.get(state, self._STYLES["idle"])
        self.setStyleSheet(style + " border-radius: 9px; padding: 2px 10px; font-weight: bold;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.adjustSize()


def human_size(num: float) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"
