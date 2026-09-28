"""Timer-based scheduler, Déjà Dup style: daily/weekly at a chosen time."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

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
    hour, minute = _parse_time(cfg.time)
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cfg.mode is ScheduleMode.DAILY:
        if today > now:
            return today
        return today + _dt.timedelta(days=1)
    if cfg.mode is ScheduleMode.WEEKLY:
        weekdays = sorted(set(cfg.weekdays)) or [1]
        for offset in range(8):
            candidate = today + _dt.timedelta(days=offset)
            if candidate.weekday() not in weekdays:
                continue
            if candidate > now:
                return candidate
        return None
    return None


def _parse_time(value: str) -> tuple:
    try:
        hour, minute = str(value).split(":", 1)
        hour = max(0, min(23, int(hour)))
        minute = max(0, min(59, int(minute)))
    except (ValueError, TypeError):
        hour, minute = 12, 0
    return hour, minute


class Scheduler(QObject):
    """Checks once a minute whether a backup is due."""

    backup_due = pyqtSignal()

    def __init__(self, config: ScheduleConfig, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._timer = QTimer(self)
        self._timer.setInterval(_MINUTE)
        self._timer.timeout.connect(self._on_tick)
        self._next_run: Optional[_dt.datetime] = None
        self._paused = False
        self._last_fired: Optional[_dt.datetime] = None

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

    def next_run(self) -> Optional[_dt.datetime]:
        return self._next_run

    def _on_tick(self) -> None:
        if self._paused or self._config.mode is ScheduleMode.OFF:
            return
        now = _dt.datetime.now()
        if self._next_run is None:
            self.recompute()
            return
        if now < self._next_run:
            return
        self._last_fired = now
        self.recompute()
        self.backup_due.emit()
