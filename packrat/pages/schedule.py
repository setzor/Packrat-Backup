"""Schedule page: daily/weekly timing, Déjà Dup style."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..settings import ScheduleMode

_WEEKDAYS = [
    ("Mon", 0),
    ("Tue", 1),
    ("Wed", 2),
    ("Thu", 3),
    ("Fri", 4),
    ("Sat", 5),
    ("Sun", 6),
]


class SchedulePage(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("When to back up")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        mode_box = QGroupBox("Backup frequency")
        mode_layout = QVBoxLayout(mode_box)
        self._off_radio = QRadioButton("Manually only")
        self._daily_radio = QRadioButton("Every day")
        self._weekly_radio = QRadioButton("Every week")
        self._group = QButtonGroup(self)
        for radio in (self._off_radio, self._daily_radio, self._weekly_radio):
            self._group.addButton(radio)
            radio.toggled.connect(self._on_mode_changed)
            mode_layout.addWidget(radio)
        root.addWidget(mode_box)

        time_box = QGroupBox("Time")
        time_layout = QHBoxLayout(time_box)
        time_layout.addWidget(QLabel("Start backups at:"))
        self._time_combo = QComboBox()
        for hour in range(24):
            for minute in (0, 30):
                self._time_combo.addItem(f"{hour:02d}:{minute:02d}")
        self._time_combo.currentTextChanged.connect(self.changed.emit)
        time_layout.addWidget(self._time_combo)
        time_layout.addStretch(1)
        root.addWidget(time_box)

        days_box = QGroupBox("Days of the week (weekly mode)")
        days_layout = QHBoxLayout(days_box)
        self._day_checks = []
        for label, value in _WEEKDAYS:
            check = QCheckBox(label)
            check.stateChanged.connect(self.changed.emit)
            self._day_checks.append((check, value))
            days_layout.addWidget(check)
        root.addWidget(days_box)
        root.addStretch(1)

    def _on_mode_changed(self) -> None:
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(weekly)
        self.changed.emit()

    # ------------------------------------------------------------------ state
    def load(self, schedule_cfg) -> None:
        blockers = [QSignalBlocker(widget) for widget in self._blocked_widgets()]
        if schedule_cfg.mode is ScheduleMode.OFF:
            self._off_radio.setChecked(True)
        elif schedule_cfg.mode is ScheduleMode.DAILY:
            self._daily_radio.setChecked(True)
        else:
            self._weekly_radio.setChecked(True)
        index = self._time_combo.findText(schedule_cfg.time)
        self._time_combo.setCurrentIndex(index if index >= 0 else 24)
        for check, value in self._day_checks:
            check.setChecked(value in schedule_cfg.weekdays)
        for blocker in blockers:
            blocker.unblock()
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(weekly)

    def _blocked_widgets(self):
        widgets = [self._off_radio, self._daily_radio, self._weekly_radio, self._time_combo]
        widgets.extend(check for check, _value in self._day_checks)
        return widgets

    def save(self):
        if self._off_radio.isChecked():
            mode = ScheduleMode.OFF
        elif self._daily_radio.isChecked():
            mode = ScheduleMode.DAILY
        else:
            mode = ScheduleMode.WEEKLY
        weekdays = [value for check, value in self._day_checks if check.isChecked()]
        return {
            "mode": mode,
            "time": self._time_combo.currentText(),
            "weekdays": weekdays or [1],
        }
