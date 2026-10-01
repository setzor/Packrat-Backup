"""Schedule page: daily/weekly timing, Déjà Dup style."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
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
    clean_now_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("When to back up")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        self._pause_check = QCheckBox("Pause scheduled backups")
        self._pause_check.setToolTip(
            "Keep this schedule but skip automatic backups until you untick this.\n"
            "Your schedule settings are remembered."
        )
        self._pause_check.toggled.connect(self._on_pause_toggled)
        self._pause_check.toggled.connect(self.changed.emit)
        root.addWidget(self._pause_check)

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

        retention_box = QGroupBox("How long to keep old backups")
        retention_layout = QVBoxLayout(retention_box)
        retention_hint = QLabel(
            "Old backups beyond these limits are removed. One backup of each "
            "period is always kept, so you never lose every restore point."
        )
        retention_hint.setStyleSheet("color: #666;")
        retention_hint.setWordWrap(True)
        retention_layout.addWidget(retention_hint)
        self._keep_daily_spin = QSpinBox()
        self._keep_daily_spin.setRange(0, 365)
        self._keep_daily_spin.setSuffix(" days")
        self._keep_weekly_spin = QSpinBox()
        self._keep_weekly_spin.setRange(0, 52)
        self._keep_weekly_spin.setSuffix(" weeks")
        self._keep_monthly_spin = QSpinBox()
        self._keep_monthly_spin.setRange(0, 120)
        self._keep_monthly_spin.setSuffix(" months")
        self._keep_yearly_spin = QSpinBox()
        self._keep_yearly_spin.setRange(0, 100)
        self._keep_yearly_spin.setSuffix(" years")
        for spin in (
            self._keep_daily_spin,
            self._keep_weekly_spin,
            self._keep_monthly_spin,
            self._keep_yearly_spin,
        ):
            spin.valueChanged.connect(self.changed.emit)
            spin.setMinimumWidth(110)

        retention_grid = QGridLayout()
        retention_grid.setHorizontalSpacing(32)
        retention_grid.setVerticalSpacing(12)
        retention_grid.addWidget(QLabel("Keep daily:"), 0, 0)
        retention_grid.addWidget(self._keep_daily_spin, 0, 1)
        retention_grid.addWidget(QLabel("Keep weekly:"), 0, 2)
        retention_grid.addWidget(self._keep_weekly_spin, 0, 3)
        retention_grid.addWidget(QLabel("Keep monthly:"), 1, 0)
        retention_grid.addWidget(self._keep_monthly_spin, 1, 1)
        retention_grid.addWidget(QLabel("Keep yearly:"), 1, 2)
        retention_grid.addWidget(self._keep_yearly_spin, 1, 3)
        retention_grid.setColumnStretch(4, 1)
        retention_layout.addLayout(retention_grid)

        self._auto_prune_check = QCheckBox("Automatically clean up after each backup")
        self._auto_prune_check.setToolTip(
            "Runs the cleanup in the background after every successful backup.\n"
            "Disable it to keep everything forever."
        )
        self._auto_prune_check.toggled.connect(self.changed.emit)
        retention_layout.addWidget(self._auto_prune_check)

        self._clean_now_button = QPushButton("Clean Up Now")
        self._clean_now_button.clicked.connect(self.clean_now_requested.emit)
        self._clean_now_button.setToolTip(
            "Remove backups older than the limits above and free their space.\n"
            "This marks old snapshots for removal and repacks the repository, "
            "which can take a while on large repositories."
        )
        clean_row = QHBoxLayout()
        clean_row.addWidget(self._clean_now_button)
        clean_row.addStretch(1)
        retention_layout.addLayout(clean_row)
        root.addWidget(retention_box)
        root.addStretch(1)

    def _on_mode_changed(self) -> None:
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(weekly)
        self._apply_pause_state()
        self.changed.emit()

    def _on_pause_toggled(self, checked: bool) -> None:
        self._apply_pause_state()

    def _apply_pause_state(self) -> None:
        paused = self._pause_check.isChecked()
        for widget in self._schedule_widgets():
            widget.setEnabled(not paused)
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(not paused and weekly)

    def set_cleaning(self, cleaning: bool) -> None:
        self._clean_now_button.setText("Cleaning…" if cleaning else "Clean Up Now")
        self._clean_now_button.setEnabled(not cleaning)

    def _schedule_widgets(self):
        widgets = [self._off_radio, self._daily_radio, self._weekly_radio, self._time_combo]
        widgets.extend(check for check, _value in self._day_checks)
        return widgets

    # ------------------------------------------------------------------ state
    def load(self, schedule_cfg, paused: bool = False, settings=None) -> None:
        blockers = [QSignalBlocker(widget) for widget in self._blocked_widgets()]
        if settings is not None:
            for spin, value in (
                (self._keep_daily_spin, settings.keep_daily),
                (self._keep_weekly_spin, settings.keep_weekly),
                (self._keep_monthly_spin, settings.keep_monthly),
                (self._keep_yearly_spin, settings.keep_yearly),
            ):
                spin.blockSignals(True)
                spin.setValue(int(value))
                spin.blockSignals(False)
            self._auto_prune_check.blockSignals(True)
            self._auto_prune_check.setChecked(bool(settings.auto_prune))
            self._auto_prune_check.blockSignals(False)
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(bool(paused))
        self._pause_check.blockSignals(False)
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
        self._apply_pause_state()

    def _blocked_widgets(self):
        widgets = [self._schedule_widgets()]
        return widgets[0]

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
            "paused": self._pause_check.isChecked(),
            "keep_daily": self._keep_daily_spin.value(),
            "keep_weekly": self._keep_weekly_spin.value(),
            "keep_monthly": self._keep_monthly_spin.value(),
            "keep_yearly": self._keep_yearly_spin.value(),
            "auto_prune": self._auto_prune_check.isChecked(),
        }
