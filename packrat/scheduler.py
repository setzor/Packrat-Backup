"""Timer-based scheduler, Déjà Dup style: hourly/daily/weekly or custom."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .guards import check_guards
from .settings import ScheduleConfig, ScheduleMode

log = logging.getLogger(__name__)

_MINUTE = 60 * 1000


def next_run_time(
    cfg: ScheduleConfig, now: Optional[_dt.datetime] = None
) -> Optional[_dt.datetime]:
    """Compute the next scheduled backup datetime, or None when off."""
    if cfg.mode is ScheduleMode.OFF:
        return None
    now = now or _dt.datetime.now()
    if cfg.mode is ScheduleMode.HOURLY:
        return (now + _dt.timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
    if cfg.mode is ScheduleMode.INTERVAL:
        hours = max(1, int(getattr(cfg, "interval_hours", 6) or 6))
        hour, minute = _parse_time(getattr(cfg, "interval_start", "12:00"))
        base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        while base <= now:
            base += _dt.timedelta(hours=hours)
        return base
    hour, minute = _parse_time(cfg.time)
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cfg.mode is ScheduleMode.DAILY:
        if today > now:
            return today
        return today + _dt.timedelta(days=1)
    if cfg.mode is ScheduleMode.WEEKLY:
        weekdays = _valid_weekdays(cfg.weekdays)
        if not weekdays:
            return None
        for offset in range(8):
            candidate = today + _dt.timedelta(days=offset)
            if candidate.weekday() in weekdays and candidate > now:
                return candidate
        return None
    return None


def previous_run_time(
    cfg: ScheduleConfig, now: Optional[_dt.datetime] = None
) -> Optional[_dt.datetime]:
    """Compute the most recent scheduled datetime at or before now, or None."""
    if cfg.mode is ScheduleMode.OFF:
        return None
    now = now or _dt.datetime.now()
    if cfg.mode is ScheduleMode.HOURLY:
        return now.replace(minute=0, second=0, microsecond=0)
    if cfg.mode is ScheduleMode.INTERVAL:
        hours = max(1, int(getattr(cfg, "interval_hours", 6) or 6))
        hour, minute = _parse_time(getattr(cfg, "interval_start", "12:00"))
        base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        while base > now:
            base -= _dt.timedelta(hours=hours)
        return base
    hour, minute = _parse_time(cfg.time)
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cfg.mode is ScheduleMode.DAILY:
        return today if today <= now else today - _dt.timedelta(days=1)
    if cfg.mode is ScheduleMode.WEEKLY:
        weekdays = _valid_weekdays(cfg.weekdays)
        if not weekdays:
            return None
        for offset in range(8):
            candidate = today - _dt.timedelta(days=offset)
            if candidate.weekday() in weekdays and candidate <= now:
                return candidate
        return None
    return None


def _valid_weekdays(weekdays) -> tuple:
    """Normalise the configured weekday list to valid Python weekday numbers."""
    values = set()
    for day in weekdays or []:
        try:
            day = int(day)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            values.add(day)
    return tuple(sorted(values))


def _parse_time(value: str) -> tuple:
    try:
        hour, minute = str(value).split(":", 1)
        hour = max(0, min(23, int(hour)))
        minute = max(0, min(59, int(minute)))
    except (ValueError, TypeError):
        hour, minute = 12, 0
    return hour, minute


class Scheduler(QObject):
    """Checks once a minute whether a backup is due.

    Guards (battery/metered network) hold the due slot and retry every
    minute until the block clears, then fire; the backup runs late
    rather than being skipped.
    """

    backup_due = pyqtSignal()
    guard_block_cleared = pyqtSignal()
    deferred_changed = pyqtSignal(bool)

    def __init__(self, config: ScheduleConfig, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._timer = QTimer(self)
        self._timer.setInterval(_MINUTE)
        self._timer.timeout.connect(self._on_tick)
        self._next_run: Optional[_dt.datetime] = None
        self._paused = False
        self._last_fired: Optional[_dt.datetime] = None
        self._skip_on_battery = False
        self._skip_on_metered = False
        self._block_active = False
        self._busy_check = None

    def set_guards(self, skip_on_battery: bool, skip_on_metered: bool) -> None:
        self._skip_on_battery = bool(skip_on_battery)
        self._skip_on_metered = bool(skip_on_metered)

    def set_busy_check(self, check) -> None:
        """Provide a callable returning True while a backup job is running.

        A due slot is held (deferred) while a job runs instead of being
        dropped, so the backup runs right after the current one ends.
        """
        self._busy_check = check

    def config(self) -> ScheduleConfig:
        return self._config

    def start(self) -> None:
        self.recompute()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)

    def is_paused(self) -> bool:
        return self._paused

    def recompute(self) -> None:
        self._next_run = next_run_time(self._config)
        if self._next_run:
            log.info("Next backup scheduled for %s", self._next_run)

    def missed_backup(
        self, last_backup: Optional[_dt.datetime], now: Optional[_dt.datetime] = None
    ) -> bool:
        """True when the scheduled slot since the last completed backup was missed."""
        if self._paused or self._config.mode is ScheduleMode.OFF:
            return False
        if last_backup is None:
            return False
        due = previous_run_time(self._config, now)
        return due is not None and last_backup < due

    def next_run(self) -> Optional[_dt.datetime]:
        return self._next_run

    def is_deferred(self) -> bool:
        """True when a backup is due but held back by a guard."""
        return self._block_active

    def _on_tick(self) -> None:
        if self._paused or self._config.mode is ScheduleMode.OFF:
            self._block_active = False
            return
        now = _dt.datetime.now()
        if self._next_run is None:
            self.recompute()
            return
        if now < self._next_run:
            return
        if self._busy_check is not None:
            try:
                busy = bool(self._busy_check())
            except Exception:
                busy = False
            if busy:
                if not self._block_active:
                    log.info("Backup job already running; deferring due slot")
                    self._block_active = True
                    self.deferred_changed.emit(True)
                return
        block = check_guards(self._skip_on_battery, self._skip_on_metered)
        if block is not None:
            if not self._block_active:
                log.info("Scheduled backup due but blocked: %s", block)
                self._block_active = True
                self.deferred_changed.emit(True)
            return
        if self._block_active:
            log.info("Guard cleared; starting deferred backup")
            self._block_active = False
            self.deferred_changed.emit(False)
            self.guard_block_cleared.emit()
        self._last_fired = now
        self.recompute()
        self.backup_due.emit()
