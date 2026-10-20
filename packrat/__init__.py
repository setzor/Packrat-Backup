"""Packrat Backup - a friendly, restic-based backup app for KDE Plasma."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("packrat")
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0+dev"

APP_NAME = "Packrat Backup"
APP_ID = "io.github.setzor.PackratBackup"
