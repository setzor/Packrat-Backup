"""Preferences page: application behaviour settings."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class PreferencesPage(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Preferences")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        behaviour_box = QGroupBox("Application behaviour")
        behaviour_layout = QVBoxLayout(behaviour_box)

        self._close_to_tray_check = QCheckBox(
            "Keep running in the system tray when the window is closed"
        )
        self._close_to_tray_check.stateChanged.connect(self._on_changed)
        behaviour_layout.addWidget(self._close_to_tray_check)

        tray_hint = QLabel(
            "When enabled, closing the window hides it and Packrat keeps "
            "running in the tray (scheduled backups still fire). When "
            "disabled, closing the window quits Packrat entirely — you can "
            "still quit from the tray with this enabled."
        )
        tray_hint.setWordWrap(True)
        tray_hint.setStyleSheet("color: #555;")
        behaviour_layout.addWidget(tray_hint)

        self._run_at_startup_check = QCheckBox("Start Packrat automatically at login")
        self._run_at_startup_check.stateChanged.connect(self._on_changed)
        behaviour_layout.addWidget(self._run_at_startup_check)

        startup_hint = QLabel(
            "Adds Packrat to your desktop session's autostart entries so the "
            "tray agent and schedule are active from the moment you log in."
        )
        startup_hint.setWordWrap(True)
        startup_hint.setStyleSheet("color: #555;")
        behaviour_layout.addWidget(startup_hint)

        root.addWidget(behaviour_box)
        root.addStretch(1)

    def _on_changed(self) -> None:
        self.changed.emit()

    # ------------------------------------------------------------------ state
    def load(self, settings) -> None:
        for check in (self._close_to_tray_check, self._run_at_startup_check):
            check.blockSignals(True)
        self._close_to_tray_check.setChecked(settings.close_to_tray)
        self._run_at_startup_check.setChecked(settings.run_at_startup)
        for check in (self._close_to_tray_check, self._run_at_startup_check):
            check.blockSignals(False)

    def save(self):
        return {
            "close_to_tray": self._close_to_tray_check.isChecked(),
            "run_at_startup": self._run_at_startup_check.isChecked(),
        }
