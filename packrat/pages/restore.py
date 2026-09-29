"""Restore page: pick a snapshot and a target folder."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..humanize import format_snapshot_time


def _folders_text(snapshot: dict) -> str:
    """Human summary of what a snapshot contains."""
    paths = snapshot.get("paths") or []
    if not paths:
        return "unknown"
    home = os.path.expanduser("~")
    shortened = []
    for path in paths[:4]:
        if path == home:
            shortened.append("~")
        elif path.startswith(home + "/"):
            shortened.append("~" + path[len(home) :])
        else:
            shortened.append(path)
    text = ", ".join(shortened)
    if len(paths) > 4:
        text += f" (+{len(paths) - 4} more)"
    return text


class RestorePage(QWidget):
    refresh_requested = pyqtSignal()
    restore_requested = pyqtSignal(str, str)
    browse_requested = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Restore files")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel(
            "Each snapshot is a full copy of your files at that moment — "
            "pick one and choose where to put it."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        root.addWidget(hint)

        snapshots_box = QGroupBox("Available snapshots")
        snapshots_layout = QVBoxLayout(snapshots_box)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["When", "Folders backed up", "ID"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setWordWrap(False)
        snapshots_layout.addWidget(self._table)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        self._loading_label = QLabel("Loading snapshots…")
        self._loading_label.setStyleSheet("color: #666; font-style: italic;")
        self._loading_label.setVisible(False)
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setVisible(False)
        self._loading_bar.setFixedHeight(6)

        refresh_row = QHBoxLayout()
        refresh_row.addWidget(self._refresh_button)
        refresh_row.addWidget(self._loading_label)
        refresh_row.addWidget(self._loading_bar, 1)
        snapshots_layout.addLayout(refresh_row)

        browse_row = QHBoxLayout()
        self._browse_button = QPushButton("Browse Contents…")
        self._browse_button.clicked.connect(self._on_browse)
        self._browse_hint = QLabel(
            "Open the selected snapshot to see exactly which files it contains."
        )
        self._browse_hint.setStyleSheet("color: #666;")
        browse_row.addWidget(self._browse_button)
        browse_row.addWidget(self._browse_hint, 1)
        snapshots_layout.addLayout(browse_row)

        self._restore_progress_bar = QProgressBar()
        self._restore_progress_bar.setRange(0, 100)
        self._restore_progress_bar.setVisible(False)
        self._restore_progress_label = QLabel("")
        self._restore_progress_label.setStyleSheet("color: #666;")
        self._restore_progress_label.setVisible(False)
        restore_progress_row = QHBoxLayout()
        restore_progress_row.addWidget(self._restore_progress_bar, 1)
        restore_progress_row.addWidget(self._restore_progress_label)
        snapshots_layout.addLayout(restore_progress_row)
        root.addWidget(snapshots_box)

        target_box = QGroupBox("Restore into folder")
        target_layout = QHBoxLayout(target_box)
        self._target_edit = QLineEdit()
        self._target_edit.setText(os.path.expanduser("~/restored"))
        self._browse_button = QPushButton("Browse…")
        self._browse_button.clicked.connect(self._on_browse)
        target_layout.addWidget(self._target_edit, 1)
        target_layout.addWidget(self._browse_button)
        root.addWidget(target_box)

        self._restore_button = QPushButton("Restore Selected Snapshot")
        self._restore_button.setMinimumHeight(44)
        self._restore_button.clicked.connect(self._on_restore)
        root.addWidget(self._restore_button)
        root.addStretch(1)

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose a restore destination",
            self._target_edit.text() or os.path.expanduser("~"),
        )
        if directory:
            self._target_edit.setText(directory)

    def _on_browse(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 2)
        time_item = self._table.item(row, 0)
        if item is None:
            return
        self.browse_requested.emit(item.text(), time_item.text() if time_item else "")

    def _on_restore(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 2)
        if item is None:
            return
        self.restore_requested.emit(item.text(), self._target_edit.text().strip())

    # ------------------------------------------------------------------ state
    def set_snapshots(self, snapshots) -> None:
        self._table.setRowCount(0)
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(
                row, 0, QTableWidgetItem(format_snapshot_time(str(snapshot.get("time", ""))))
            )
            self._table.setItem(row, 1, QTableWidgetItem(_folders_text(snapshot)))
            self._table.setItem(row, 2, QTableWidgetItem(str(snapshot.get("short_id", ""))))

    def set_enabled_state(self, running: bool) -> None:
        self._restore_button.setEnabled(not running)
        self._refresh_button.setEnabled(not running)
        self._browse_button.setEnabled(not running)

    def set_loading(self, loading: bool) -> None:
        self._loading_label.setVisible(loading)
        self._loading_bar.setVisible(loading)
        self._refresh_button.setEnabled(not loading)
        self._browse_button.setEnabled(not loading)

    def set_restore_progress(self, percent: int, message: str) -> None:
        visible = percent >= 0 or bool(message)
        self._restore_progress_bar.setVisible(visible)
        self._restore_progress_label.setVisible(visible)
        if percent >= 0:
            self._restore_progress_bar.setRange(0, 100)
            self._restore_progress_bar.setValue(percent)
            self._restore_progress_label.setText(
                f"Restoring… {percent}%" + (f" — {message}" if message else "")
            )
        else:
            self._restore_progress_bar.setRange(0, 0)
            self._restore_progress_label.setText(message or "Restoring…")

    def clear_restore_progress(self) -> None:
        self._restore_progress_bar.setVisible(False)
        self._restore_progress_label.setVisible(False)
