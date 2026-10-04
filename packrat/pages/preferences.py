"""Preferences page: application behaviour settings."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
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

        performance_box = QGroupBox("Performance")
        performance_layout = QHBoxLayout(performance_box)
        performance_layout.addWidget(QLabel("Re-list snapshots on the Restore page at most every:"))
        self._restore_refresh_spin = QSpinBox()
        self._restore_refresh_spin.setRange(0, 1440)
        self._restore_refresh_spin.setSuffix(" min")
        self._restore_refresh_spin.setSpecialValueText("Always refresh")
        self._restore_refresh_spin.setToolTip(
            "How long a loaded snapshot list is reused when you revisit the "
            'Restore page.\\nSet to "Always refresh" to reload every visit '
            "(slower on cloud destinations).\\nThe list always reloads after a "
            "backup finishes or when you click Refresh."
        )
        self._restore_refresh_spin.valueChanged.connect(self._on_changed)
        performance_layout.addWidget(self._restore_refresh_spin)
        performance_layout.addStretch(1)
        root.addWidget(performance_box)

        verify_box = QGroupBox("Verified restores")
        verify_layout = QHBoxLayout(verify_box)
        verify_layout.addWidget(QLabel("After each backup, prove it restorable by re-reading:"))
        self._verify_combo = QComboBox()
        self._verify_combo.addItem("A random sample of the data (recommended)", "sample")
        self._verify_combo.addItem("All of the data (slowest, most thorough)", "full")
        self._verify_combo.addItem("Nothing (turn verification off)", "off")
        self._verify_combo.setToolTip(
            "Verification reads back data after each backup and confirms its "
            "checksums, so Packrat can prove the backup is restorable instead "
            "of trusting it. The sample mode reads a random 10% of data "
            "packs — a good balance of safety and speed for large repositories."
        )
        self._verify_combo.currentIndexChanged.connect(self._on_changed)
        verify_layout.addWidget(self._verify_combo)
        verify_layout.addStretch(1)
        root.addWidget(verify_box)

        change_box = QGroupBox("Change detection")
        change_layout = QHBoxLayout(change_box)
        self._change_check = QCheckBox("Warn when a backup changes more than:")
        self._change_check.setToolTip(
            "After each backup, Packrat compares how many files changed against "
            "the previous snapshot. A sudden mass change can mean ransomware "
            "encryption or an accidental edit, so Packrat warns loudly instead "
            "of silently backing up the damage."
        )
        self._change_check.stateChanged.connect(self._on_changed)
        change_layout.addWidget(self._change_check)
        self._change_spin = QSpinBox()
        self._change_spin.setRange(5, 100)
        self._change_spin.setSuffix("% of files")
        self._change_spin.valueChanged.connect(self._on_changed)
        change_layout.addWidget(self._change_spin)
        change_layout.addStretch(1)
        root.addWidget(change_box)
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
        self._restore_refresh_spin.blockSignals(True)
        self._restore_refresh_spin.setValue(int(settings.restore_refresh_minutes))
        self._restore_refresh_spin.blockSignals(False)
        self._verify_combo.blockSignals(True)
        index = self._verify_combo.findData(settings.verify_after_backup)
        self._verify_combo.setCurrentIndex(index if index >= 0 else 0)
        self._verify_combo.blockSignals(False)
        self._change_check.blockSignals(True)
        self._change_check.setChecked(settings.change_detection)
        self._change_check.blockSignals(False)
        self._change_spin.blockSignals(True)
        self._change_spin.setValue(int(settings.changed_files_threshold))
        self._change_spin.blockSignals(False)

    def save(self):
        return {
            "close_to_tray": self._close_to_tray_check.isChecked(),
            "run_at_startup": self._run_at_startup_check.isChecked(),
            "restore_refresh_minutes": self._restore_refresh_spin.value(),
            "verify_after_backup": self._verify_combo.currentData(),
            "change_detection": self._change_check.isChecked(),
            "changed_files_threshold": self._change_spin.value(),
        }
