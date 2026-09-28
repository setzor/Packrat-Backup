"""Application-wide settings stored in an INI file under ~/.config."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

from PyQt6.QtCore import QSettings

from .paths import config_dir


class ScheduleMode(Enum):
    OFF = "off"
    DAILY = "daily"
    WEEKLY = "weekly"


class Backend(Enum):
    LOCAL = "local"
    RCLONE = "rclone"


@dataclass
class BackendConfig:
    """Where backups are stored."""

    backend: Backend = Backend.LOCAL
    local_path: str = os.path.expanduser("~/.local/share/packrat/backups")
    rclone_remote: str = ""
    rclone_path: str = "packrat-backups"


@dataclass
class ScheduleConfig:
    mode: ScheduleMode = ScheduleMode.OFF
    time: str = "12:00"
    weekdays: List[int] = field(default_factory=lambda: [1])


class Settings:
    """Load/save of all Packrat options via QSettings.

    Sensible defaults are exposed as attributes so the UI and the
    backend can rely on always-populated values.
    """

    _KEYS = (
        "first_run_done",
        "folders",
        "exclude_patterns",
        "backend_kind",
        "local_path",
        "rclone_remote",
        "rclone_path",
        "schedule_mode",
        "schedule_time",
        "schedule_weekdays",
        "last_backup_time",
        "next_backup_time",
        "keep_hourly",
        "keep_daily",
        "keep_weekly",
        "keep_monthly",
        "keep_yearly",
        "keep_within",
    )

    def __init__(self) -> None:
        self._settings = QSettings("Packrat", "Packrat Backup")
        self.first_run_done: bool = False
        self.close_to_tray: bool = True
        self.run_at_startup: bool = True
        self.folders: List[str] = []
        self.exclude_patterns: List[str] = [
            "~/.cache",
            "~/.local/share/Trash",
            "**/*.tmp",
        ]
        self.backend_cfg = BackendConfig()
        self.schedule = ScheduleConfig()
        self.last_backup_time: str = ""
        self.next_backup_time: str = ""
        self.keep_hourly: int = 0
        self.keep_daily: int = 7
        self.keep_weekly: int = 5
        self.keep_monthly: int = 12
        self.keep_yearly: int = 3
        self.keep_within: str = "1m"
        self._load()

    def _expand(self, path: str) -> str:
        return os.path.expanduser(path) if path else path

    def _load(self) -> None:
        s = self._settings
        self.first_run_done = to_bool(s.value("first_run_done", False, type=bool))
        self.close_to_tray = to_bool(s.value("close_to_tray", True, type=bool))
        self.run_at_startup = to_bool(s.value("run_at_startup", True, type=bool))
        self.folders = _to_str_list(s.value("folders", ""))
        raw_excludes = s.value("exclude_patterns", "", type=str)
        if raw_excludes:
            self.exclude_patterns = _to_str_list(raw_excludes)
        else:
            self.exclude_patterns = [
                "~/.cache",
                "~/.local/share/Trash",
                "**/*.tmp",
            ]
        kind = s.value("backend_kind", Backend.LOCAL.value, type=str)
        try:
            self.backend_cfg.backend = Backend(kind)
        except ValueError:
            self.backend_cfg.backend = Backend.LOCAL
        self.backend_cfg.local_path = s.value("local_path", self.backend_cfg.local_path, type=str)
        self.backend_cfg.rclone_remote = s.value("rclone_remote", "", type=str)
        self.backend_cfg.rclone_path = s.value("rclone_path", "packrat-backups", type=str)
        mode = s.value("schedule_mode", ScheduleMode.OFF.value, type=str)
        try:
            self.schedule.mode = ScheduleMode(mode)
        except ValueError:
            self.schedule.mode = ScheduleMode.OFF
        self.schedule.time = s.value("schedule_time", "12:00", type=str)
        self.schedule.weekdays = _to_int_list(s.value("schedule_weekdays", "1"))
        self.last_backup_time = s.value("last_backup_time", "", type=str)
        self.next_backup_time = s.value("next_backup_time", "", type=str)
        self.keep_hourly = s.value("keep_hourly", 0, type=int)
        self.keep_daily = s.value("keep_daily", 7, type=int)
        self.keep_weekly = s.value("keep_weekly", 5, type=int)
        self.keep_monthly = s.value("keep_monthly", 12, type=int)
        self.keep_yearly = s.value("keep_yearly", 3, type=int)
        self.keep_within = s.value("keep_within", "1m", type=str)

    def save(self) -> None:
        s = self._settings
        s.setValue("first_run_done", self.first_run_done)
        s.setValue("close_to_tray", self.close_to_tray)
        s.setValue("run_at_startup", self.run_at_startup)
        s.setValue("folders", ",".join(self.folders))
        s.setValue("exclude_patterns", ",".join(self.exclude_patterns))
        s.setValue("backend_kind", self.backend_cfg.backend.value)
        s.setValue("local_path", self.backend_cfg.local_path)
        s.setValue("rclone_remote", self.backend_cfg.rclone_remote)
        s.setValue("rclone_path", self.backend_cfg.rclone_path)
        s.setValue("schedule_mode", self.schedule.mode.value)
        s.setValue("schedule_time", self.schedule.time)
        s.setValue("schedule_weekdays", ",".join(str(d) for d in self.schedule.weekdays))
        s.setValue("last_backup_time", self.last_backup_time)
        s.setValue("next_backup_time", self.next_backup_time)
        s.setValue("keep_hourly", self.keep_hourly)
        s.setValue("keep_daily", self.keep_daily)
        s.setValue("keep_weekly", self.keep_weekly)
        s.setValue("keep_monthly", self.keep_monthly)
        s.setValue("keep_yearly", self.keep_yearly)
        s.setValue("keep_within", self.keep_within)
        s.sync()

    def add_folder(self, path: str) -> None:
        expanded = self._expand(path)
        if expanded and expanded not in self.folders:
            self.folders.append(expanded)

    def remove_folder(self, path: str) -> None:
        self.folders = [f for f in self.folders if f != path]

    def backend_summary(self) -> str:
        if self.backend_cfg.backend is Backend.LOCAL:
            return self._expand(self.backend_cfg.local_path)
        remote = self.backend_cfg.rclone_remote
        sub = self.backend_cfg.rclone_path.strip("/")
        return f"{remote}:{sub}" if remote else "not configured"

    def is_backend_configured(self) -> bool:
        if self.backend_cfg.backend is Backend.LOCAL:
            return bool(self._expand(self.backend_cfg.local_path))
        return bool(self.backend_cfg.rclone_remote)


def to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


def _to_str_list(raw) -> List[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def _to_int_list(raw) -> List[int]:
    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw).split(",")
    result: List[int] = []
    for item in values:
        try:
            result.append(int(str(item)))
        except ValueError:
            continue
    return result


def default_config_path() -> Path:
    return config_dir() / "packrat.conf"


def _autostart_exec() -> str:
    """Best-effort command line for the autostart entry."""
    import shutil
    import sys

    exe = shutil.which("packrat")
    if exe:
        return f"{exe} --tray"
    python = sys.executable or "python3"
    return f"{python} -m packrat --tray"


def update_autostart(run_at_startup: bool) -> bool:
    """Install or remove the autostart .desktop entry for the tray agent."""
    autostart = (
        Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "autostart"
    )
    target = autostart / "org.packrat.Backup.desktop"
    try:
        if not run_at_startup:
            if target.exists():
                target.unlink()
            return True
        autostart.mkdir(parents=True, exist_ok=True)
        entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Packrat Backup\n"
            f"Exec={_autostart_exec()}\n"
            "Icon=org.packrat.Backup\n"
            "Terminal=false\n"
            "X-KDE-autostart-after=panel\n"
            "Categories=System;FileTools;Archiving;Backup;\n"
        )
        if not target.exists() or target.read_text() != entry:
            target.write_text(entry)
        return True
    except OSError:
        return False
