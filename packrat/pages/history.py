"""History page: recent backup/restore runs from the activity log."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..activity import load_runs


def _status_text(entry: dict) -> str:
    if entry.get("success"):
        return "Succeeded"
    return "Failed"


def _duration_text(entry: dict) -> str:
    seconds = entry.get("duration_seconds")
    if not seconds:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


class HistoryPage(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Backup history")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel("Recent backup and restore runs, newest first.")
        hint.setStyleSheet("color: #666;")
        root.addWidget(hint)

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)
        root.addWidget(self._refresh_button)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Started", "Operation", "Duration", "Status"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setWordWrap(False)
        root.addWidget(self._table, 1)

        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet("color: #666;")
        self._detail_label.setWordWrap(True)
        root.addWidget(self._detail_label)

        self._table.currentItemChanged.connect(self._on_selection)

    def refresh(self) -> None:
        runs = load_runs()
        self._table.setRowCount(0)
        for entry in runs:
            row = self._table.rowCount()
            self._table.insertRow(row)
            started = str(entry.get("started_at", ""))
            date_part, _, time_part = started.partition("T")
            shown = f"{date_part} {time_part[:8]}".strip() or started
            self._table.setItem(row, 0, QTableWidgetItem(shown))
            self._table.setItem(row, 1, QTableWidgetItem(str(entry.get("operation", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(_duration_text(entry)))
            self._table.setItem(row, 3, QTableWidgetItem(_status_text(entry)))
            self._table.item(row, 3).setData(1, entry)
        self._detail_label.setText(f"{len(runs)} run{'s' if len(runs) != 1 else ''} shown.")

    def _on_selection(self, current, _previous) -> None:
        if current is None:
            self._detail_label.setText("")
            return
        row = current.row()
        item = self._table.item(row, 3)
        if item is None:
            return
        entry = item.data(1)
        if not isinstance(entry, dict):
            return
        message = str(entry.get("message", ""))
        self._detail_label.setText(message or "No details recorded.")
