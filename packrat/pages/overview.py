"""Overview page: friendly status, last/next backup, big action buttons."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..widgets import StatusBadge


def _overview_mascot():
    import os

    from PyQt6.QtGui import QPixmap

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "assets", "packrat-overview.svg")
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        96,
        96,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class _StatTile(QFrame):
    def __init__(self, caption: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self._caption = QLabel(caption)
        self._caption.setStyleSheet("color: #888; font-size: 12px;")
        self._value = QLabel("—")
        self._value.setStyleSheet("font-size: 17px; font-weight: 600;")
        self._value.setWordWrap(True)
        layout.addWidget(self._caption)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text or "—")


class OverviewPage(QWidget):
    backup_requested = pyqtSignal()
    restore_requested = pyqtSignal()
    verify_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        self._title = QLabel("Your data is protected")
        self._title.setStyleSheet("font-size: 22px; font-weight: 600;")
        self._badge = StatusBadge("Not backed up yet", "warn")
        title_block.addWidget(self._title)
        title_block.addWidget(self._badge)
        header.addLayout(title_block)
        header.addStretch(1)
        mascot = QLabel()
        mascot_pixmap = _overview_mascot()
        if not mascot_pixmap.isNull():
            mascot.setPixmap(mascot_pixmap)
        header.addWidget(mascot)
        root.addLayout(header)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #666;")
        root.addWidget(self._status_label)

        info_box = QGroupBox("Backup summary")
        grid = QGridLayout(info_box)
        grid.setContentsMargins(12, 12, 12, 12)
        self._last_tile = _StatTile("Last backup")
        self._next_tile = _StatTile("Next backup")
        self._schedule_tile = _StatTile("Schedule")
        self._dest_tile = _StatTile("Destination")
        grid.addWidget(self._last_tile, 0, 0)
        grid.addWidget(self._next_tile, 0, 1)
        grid.addWidget(self._schedule_tile, 1, 0)
        grid.addWidget(self._dest_tile, 1, 1)
        root.addWidget(info_box)

        self._progress_text = QLabel("")
        self._progress_text.setVisible(False)
        self._progress_text.setWordWrap(True)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)
        root.addWidget(self._progress_text)

        actions = QHBoxLayout()
        self._backup_button = QPushButton("Back Up Now")
        self._backup_button.setMinimumHeight(44)
        self._backup_button.clicked.connect(self.backup_requested.emit)
        self._restore_button = QPushButton("Restore…")
        self._restore_button.setMinimumHeight(44)
        self._restore_button.clicked.connect(self.restore_requested.emit)
        self._verify_button = QPushButton("Verify Repository")
        self._verify_button.setMinimumHeight(44)
        self._verify_button.clicked.connect(self.verify_requested.emit)
        actions.addWidget(self._backup_button)
        actions.addWidget(self._restore_button)
        actions.addWidget(self._verify_button)
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
        schedule: str = "",
        badge_state: str = "warn",
        badge_label: str = "Not backed up yet",
    ) -> None:
        self._last_tile.set_value(last_backup)
        self._next_tile.set_value(next_backup)
        self._schedule_tile.set_value(schedule or "—")
        self._dest_tile.set_value(destination)
        self._badge.set_state(badge_state)
        self._badge.setText(badge_label)
        if running:
            self._title.setText("Backup in progress…")
            self._badge.set_state("ok")
            self._badge.setText("Running")
            self._backup_button.setEnabled(False)
        else:
            self._title.setText("Your data is protected")
            self._backup_button.setEnabled(True)

    def set_progress(self, percent: int, message: str) -> None:
        if percent < 0:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
            self._progress_text.setVisible(bool(message))
            self._progress_text.setText(message)
            return
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(percent)
        self._progress_bar.setVisible(True)
        self._progress_text.setVisible(True)
        self._progress_text.setText(f"{percent}% — {message}" if message else f"{percent}%")

    def clear_progress(self) -> None:
        self._progress_bar.setVisible(False)
        self._progress_text.setVisible(False)
        self._progress_text.setText("")

    def set_backup_enabled(self, enabled: bool) -> None:
        self._backup_button.setEnabled(enabled)

    def set_verify_enabled(self, enabled: bool) -> None:
        self._verify_button.setEnabled(enabled)

    def set_checking(self, checking: bool) -> None:
        self._verify_button.setText("Verifying…" if checking else "Verify Repository")
        self._verify_button.setEnabled(not checking)
