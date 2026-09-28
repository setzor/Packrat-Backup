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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..widgets import human_size


class RestorePage(QWidget):
    refresh_requested = pyqtSignal()
    restore_requested = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Restore files")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        snapshots_box = QGroupBox("Available snapshots")
        snapshots_layout = QVBoxLayout(snapshots_box)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["ID", "Date", "Host", "Size"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        snapshots_layout.addWidget(self._table)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self._on_refresh)
        refresh_row = QHBoxLayout()
        refresh_row.addWidget(self._refresh_button)
        refresh_row.addStretch(1)
        snapshots_layout.addLayout(refresh_row)
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

    def _on_refresh(self) -> None:
        self.refresh_requested.emit()

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose a restore destination",
            self._target_edit.text() or os.path.expanduser("~"),
        )
        if directory:
            self._target_edit.setText(directory)

    def _on_restore(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        self.restore_requested.emit(item.text(), self._target_edit.text().strip())

    # ------------------------------------------------------------------ state
    def set_snapshots(self, snapshots) -> None:
        self._table.setRowCount(0)
        for snapshot in snapshots:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(snapshot.get("short_id", ""))))
            self._table.setItem(row, 1, QTableWidgetItem(str(snapshot.get("time", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(str(snapshot.get("hostname", ""))))
            size = sum(
                info.get("size", 0)
                for info in snapshot.get("summary", {}).values()
                if isinstance(info, dict)
            )
            self._table.setItem(row, 3, QTableWidgetItem(human_size(size)))

    def set_enabled_state(self, running: bool) -> None:
        self._restore_button.setEnabled(not running)
