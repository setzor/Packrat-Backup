"""Filesystem locations used by Packrat."""

from __future__ import annotations

import os
from pathlib import Path


def _home() -> Path:
    return Path.home()


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else (_home() / ".config")
    return root / "packrat"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else (_home() / ".cache")
    return root / "packrat"


def log_dir() -> Path:
    return cache_dir() / "logs"


def default_backup_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else (_home() / ".local" / "share")
    return root / "packrat" / "backups"
