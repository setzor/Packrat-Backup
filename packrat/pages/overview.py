"""Overview page: current status, last/next backup, big action buttons."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..widgets import StatusBadge


class OverviewPage(QWidget):
    backup_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        self._title = QLabel("Your data is protected")
        self._title.setStyleSheet("font-size: 22px; font-weight: 600;")
        self._badge = StatusBadge("Not backed up yet", "warn")
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._badge)
        root.addLayout(header)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        info_box = QGroupBox("Backup summary")
        info_layout = QHBoxLayout(info_box)
        self._last_label = QLabel("Last backup: —")
        self._next_label = QLabel("Next backup: —")
        self._dest_label = QLabel("Destination: —")
        for label in (self._last_label, self._next_label, self._dest_label):
            label.setWordWrap(True)
            info_layout.addWidget(label)
        root.addWidget(info_box)

        self._progress_text = QLabel("")
        self._progress_text.setVisible(False)
        self._progress_text.setWordWrap(True)
        root.addWidget(self._progress_text)

        actions = QHBoxLayout()
        self._backup_button = QPushButton("Back Up Now")
        self._backup_button.setMinimumHeight(44)
        self._backup_button.clicked.connect(self.backup_requested.emit)
        self._restore_button = QPushButton("Restore…")
        self._restore_button.setMinimumHeight(44)
        self._restore_button.clicked.connect(self.restore_requested.emit)
        actions.addWidget(self._backup_button)
        actions.addWidget(self._restore_button)
        actions.addStretch(1)
        root.addLayout(actions)
        root.addStretch(1)

    # ------------------------------------------------------------------ updates
    def set_state(
        self,
        last_backup: str,
        next_backup: str,
        destination: str,
        running: bool,
    ) -> None:
        self._last_label.setText(f"Last backup: {last_backup or '—'}")
        self._next_label.setText(f"Next backup: {next_backup or '—'}")
        self._dest_label.setText(f"Destination: {destination}")
        if running:
            self._title.setText("Backup in progress…")
            self._badge.set_state("ok")
            self._badge.setText("Running")
            self._backup_button.setEnabled(False)
        else:
            self._title.setText("Your data is protected")
            self._badge.set_state("ok" if last_backup else "warn")
            self._badge.setText("Up to date" if last_backup else "Not backed up yet")
            self._backup_button.setEnabled(True)

    def set_progress(self, percent: int, message: str) -> None:
        if percent < 0:
            self._progress_text.setVisible(bool(message))
            self._progress_text.setText(message)
            return
        self._progress_text.setVisible(True)
        self._progress_text.setText(f"{percent}% — {message}" if message else f"{percent}%")

    def clear_progress(self) -> None:
        self._progress_text.setVisible(False)
        self._progress_text.setText("")

    def set_backup_enabled(self, enabled: bool) -> None:
        self._backup_button.setEnabled(enabled)
