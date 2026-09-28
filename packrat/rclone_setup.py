"""Guided setup helpers for rclone cloud remotes."""

from __future__ import annotations

import subprocess
from typing import Tuple

from .tools import rclone_path


def open_rclone_config_ui() -> Tuple[bool, str]:
    """Open rclone's guided configuration UI in a web browser.

    ``rclone config ui`` serves a local web page and waits; it is launched
    detached so Packrat stays responsive. Returns (opened, user message).
    """
    binary = rclone_path()
    if not binary:
        return False, (
            "rclone is not installed. Install it with your package manager "
            "(e.g. 'sudo dnf install rclone' on Fedora, 'sudo apt install "
            "rclone' on Debian/Ubuntu) and try again."
        )
    try:
        subprocess.Popen([binary, "config", "ui"])
    except OSError as exc:
        return False, (
            f"Could not start rclone's setup UI ({exc}). Run 'rclone config' "
            "in a terminal instead, then come back and click Refresh."
        )
    return True, (
        "rclone's guided setup should now be open in your browser. Choose "
        "'onedrive' (Microsoft OneDrive) or 'drive' (Google Drive), sign in, "
        "and name the remote. When you're done, come back and click Refresh."
    )


def no_remotes_help() -> str:
    return (
        "No cloud remotes are configured yet. Click 'Set up cloud storage…' "
        "to open rclone's guided setup in your browser (pick OneDrive or "
        "Google Drive and sign in), or run 'rclone config' in a terminal. "
        "When the new remote is saved, click Refresh."
    )


def rclone_missing_help() -> str:
    return (
        "rclone is not installed. Install it with your package manager "
        "(e.g. 'sudo dnf install rclone' on Fedora), then click Refresh."
    )
