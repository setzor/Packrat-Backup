"""Schedule page: daily/weekly timing, Déjà Dup style."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
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
    QScrollArea,
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

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
        self._hourly_radio = QRadioButton("Every hour")
        self._daily_radio = QRadioButton("Every day")
        self._weekly_radio = QRadioButton("Every week")
        self._interval_radio = QRadioButton("Custom interval")
        self._group = QButtonGroup(self)
        for radio in (
            self._off_radio,
            self._hourly_radio,
            self._daily_radio,
            self._weekly_radio,
            self._interval_radio,
        ):
            self._group.addButton(radio)
            radio.toggled.connect(self._on_mode_changed)
            mode_layout.addWidget(radio)
        interval_row = QHBoxLayout()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 24 * 30)
        self._interval_spin.setSuffix(" hours")
        self._interval_spin.setMinimumWidth(110)
        self._interval_spin.valueChanged.connect(self.changed.emit)
        self._interval_unit = QComboBox()
        self._interval_unit.addItem("hours", 1)
        self._interval_unit.addItem("days", 24)
        self._interval_unit.currentIndexChanged.connect(self._on_interval_unit)
        self._interval_unit.currentIndexChanged.connect(self.changed.emit)
        interval_row.addWidget(QLabel("    Run every:"))
        interval_row.addWidget(self._interval_spin)
        interval_row.addWidget(self._interval_unit)
        interval_row.addStretch(1)
        mode_layout.addLayout(interval_row)
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

        interval_time_box = QGroupBox("First run of a custom interval")
        interval_time_layout = QHBoxLayout(interval_time_box)
        interval_time_layout.addWidget(QLabel("Count the interval from:"))
        self._interval_start_combo = QComboBox()
        for hour in range(24):
            self._interval_start_combo.addItem(f"{hour:02d}:00")
        self._interval_start_combo.currentTextChanged.connect(self.changed.emit)
        interval_time_layout.addWidget(self._interval_start_combo)
        interval_time_layout.addStretch(1)
        root.addWidget(interval_time_box)

        guards_box = QGroupBox("Skip automatic backups when…")
        guards_layout = QVBoxLayout(guards_box)
        self._battery_check = QCheckBox("Running on battery power")
        self._battery_check.setToolTip(
            "Wait until the machine is plugged in. The backup starts\n"
            "automatically once power returns; it is delayed, not skipped."
        )
        self._battery_check.toggled.connect(self.changed.emit)
        self._metered_check = QCheckBox("Connected to a metered network (e.g. mobile data)")
        self._metered_check.setToolTip(
            "Wait until the connection is no longer metered. The backup\n"
            "starts automatically once you are back on an unmetered network."
        )
        self._metered_check.toggled.connect(self.changed.emit)
        guards_layout.addWidget(self._battery_check)
        guards_layout.addWidget(self._metered_check)
        root.addWidget(guards_box)

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

        self._auto_prune_check = QCheckBox("Automatically apply cleanup rules after each backup")
        self._auto_prune_check.setToolTip(
            "Applies the backup limits in the background after every successful "
            "backup.\nRepacking the repository to free space runs at most once "
            "a week (or the interval below), because it is slow on cloud "
            "destinations.\nDisable it to keep everything forever."
        )
        self._auto_prune_check.toggled.connect(self.changed.emit)
        retention_layout.addWidget(self._auto_prune_check)

        self._auto_prune_interval_spin = QSpinBox()
        self._auto_prune_interval_spin.setRange(1, 90)
        self._auto_prune_interval_spin.setSuffix(" days")
        self._auto_prune_interval_spin.setToolTip(
            "How often the full cleanup (freeing disk space by repacking) "
            "runs automatically. Between runs, old backups are only marked "
            "for removal, which is much faster on cloud destinations."
        )
        self._auto_prune_interval_spin.valueChanged.connect(self.changed.emit)
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Fully repack and free space at most every:"))
        interval_row.addWidget(self._auto_prune_interval_spin)
        interval_row.addStretch(1)
        retention_layout.addLayout(interval_row)

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
        self._update_mode_widgets()
        self._apply_pause_state()
        self.changed.emit()

    def _on_interval_unit(self) -> None:
        in_hours = self._interval_unit.currentData() == 1
        self._interval_spin.setRange(1, 24 * 30 if in_hours else 30)
        self._interval_spin.setSuffix(" hours" if in_hours else " days")

    def _update_mode_widgets(self) -> None:
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(weekly)
        interval = self._interval_radio.isChecked()
        self._interval_spin.setEnabled(interval)
        self._interval_unit.setEnabled(interval)
        self._interval_start_combo.setEnabled(interval)

    def _on_pause_toggled(self, checked: bool) -> None:
        self._apply_pause_state()

    def _apply_pause_state(self) -> None:
        paused = self._pause_check.isChecked()
        for widget in self._schedule_widgets():
            widget.setEnabled(not paused)
        weekly = self._weekly_radio.isChecked()
        for check, _value in self._day_checks:
            check.setEnabled(not paused and weekly)
        interval = self._interval_radio.isChecked()
        self._interval_spin.setEnabled(not paused and interval)
        self._interval_unit.setEnabled(not paused and interval)
        self._interval_start_combo.setEnabled(not paused and interval)

    def set_cleaning(self, cleaning: bool) -> None:
        self._clean_now_button.setText("Cleaning…" if cleaning else "Clean Up Now")
        self._clean_now_button.setEnabled(not cleaning)

    def _schedule_widgets(self):
        widgets = [
            self._off_radio,
            self._hourly_radio,
            self._daily_radio,
            self._weekly_radio,
            self._interval_radio,
            self._time_combo,
            self._interval_spin,
            self._interval_unit,
            self._interval_start_combo,
        ]
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
            self._auto_prune_interval_spin.blockSignals(True)
            self._auto_prune_interval_spin.setValue(int(settings.auto_prune_interval_days))
            self._auto_prune_interval_spin.blockSignals(False)
        if settings is not None:
            self._battery_check.blockSignals(True)
            self._battery_check.setChecked(bool(settings.skip_on_battery))
            self._battery_check.blockSignals(False)
            self._metered_check.blockSignals(True)
            self._metered_check.setChecked(bool(settings.skip_on_metered))
            self._metered_check.blockSignals(False)
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(bool(paused))
        self._pause_check.blockSignals(False)
        if schedule_cfg.mode is ScheduleMode.OFF:
            self._off_radio.setChecked(True)
        elif schedule_cfg.mode is ScheduleMode.HOURLY:
            self._hourly_radio.setChecked(True)
        elif schedule_cfg.mode is ScheduleMode.DAILY:
            self._daily_radio.setChecked(True)
        elif schedule_cfg.mode is ScheduleMode.INTERVAL:
            self._interval_radio.setChecked(True)
        else:
            self._weekly_radio.setChecked(True)
        index = self._time_combo.findText(schedule_cfg.time)
        self._time_combo.setCurrentIndex(index if index >= 0 else 24)
        hours = int(getattr(schedule_cfg, "interval_hours", 6) or 6)
        start = getattr(schedule_cfg, "interval_start", "12:00") or "12:00"
        self._interval_spin.blockSignals(True)
        if hours % 24 == 0 and hours >= 24:
            self._interval_unit.setCurrentIndex(1)
            self._interval_spin.setValue(hours // 24)
        else:
            self._interval_unit.setCurrentIndex(0)
            self._interval_spin.setValue(max(1, hours))
        self._interval_spin.blockSignals(False)
        self._on_interval_unit()
        start_index = self._interval_start_combo.findText(start)
        self._interval_start_combo.setCurrentIndex(start_index if start_index >= 0 else 12)
        for check, value in self._day_checks:
            check.setChecked(value in schedule_cfg.weekdays)
        for blocker in blockers:
            blocker.unblock()
        self._update_mode_widgets()
        self._apply_pause_state()

    def _blocked_widgets(self):
        widgets = self._schedule_widgets()
        widgets.extend(
            (
                self._pause_check,
                self._battery_check,
                self._metered_check,
            )
        )
        return widgets

    def save(self):
        if self._off_radio.isChecked():
            mode = ScheduleMode.OFF
        elif self._hourly_radio.isChecked():
            mode = ScheduleMode.HOURLY
        elif self._daily_radio.isChecked():
            mode = ScheduleMode.DAILY
        elif self._interval_radio.isChecked():
            mode = ScheduleMode.INTERVAL
        else:
            mode = ScheduleMode.WEEKLY
        interval_hours = self._interval_spin.value() * self._interval_unit.currentData()
        weekdays = [value for check, value in self._day_checks if check.isChecked()]
        return {
            "mode": mode,
            "time": self._time_combo.currentText(),
            "weekdays": weekdays or [1],
            "interval_hours": interval_hours,
            "interval_start": self._interval_start_combo.currentText(),
            "paused": self._pause_check.isChecked(),
            "skip_on_battery": self._battery_check.isChecked(),
            "skip_on_metered": self._metered_check.isChecked(),
            "keep_daily": self._keep_daily_spin.value(),
            "keep_weekly": self._keep_weekly_spin.value(),
            "keep_monthly": self._keep_monthly_spin.value(),
            "keep_yearly": self._keep_yearly_spin.value(),
            "auto_prune": self._auto_prune_check.isChecked(),
            "auto_prune_interval_days": self._auto_prune_interval_spin.value(),
        }
