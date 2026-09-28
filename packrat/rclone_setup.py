"""Guided setup helpers for rclone cloud remotes."""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Tuple

from .tools import rclone_path

_TERMINALS = (
    ("konsole", ["-e"]),
    ("gnome-terminal", ["--"]),
    ("xterm", ["-e"]),
    ("alacritty", ["-e"]),
    ("kitty", ["-e"]),
    ("wezterm", ["--", "start", "--"]),
    ("foot", ["--"]),
)


def _find_terminal() -> Optional[Tuple[str, List[str]]]:
    for name, args in _TERMINALS:
        path = shutil.which(name)
        if path:
            return path, args
    return None


def open_rclone_config_ui() -> Tuple[bool, str]:
    """Open rclone's interactive configuration in a terminal emulator.

    'rclone config' works on every rclone version and is the canonical way
    to create a remote. Returns (opened, user message).
    """
    binary = rclone_path()
    if not binary:
        return False, rclone_missing_help()
    terminal = _find_terminal()
    if terminal is None:
        return False, (
            "Packrat could not find a terminal emulator to run rclone's setup "
            "in. Please open a terminal yourself and run 'rclone config', "
            "then come back and click Refresh."
        )
    term_path, term_args = terminal
    try:
        subprocess.Popen([term_path] + term_args + [binary, "config"])
    except OSError as exc:
        return False, (
            f"Could not open a terminal for rclone setup ({exc}). Please run "
            "'rclone config' in a terminal yourself, then click Refresh."
        )
    return True, (
        "A terminal window should now be open running rclone's setup. Choose "
        "'n' for a new remote, pick 'onedrive' (Microsoft OneDrive) or "
        "'drive' (Google Drive) from the list, sign in when asked, and give "
        "the remote a name (e.g. 'onedrive'). When you're done, come back "
        "and click Refresh."
    )


def no_remotes_help() -> str:
    return (
        "No cloud remotes are configured yet. Click 'Set up cloud storage…' "
        "to open rclone's setup in a terminal (pick OneDrive or Google Drive "
        "and sign in), or run 'rclone config' yourself. When the new remote "
        "is saved, click Refresh."
    )


def rclone_missing_help() -> str:
    return (
        "rclone is not installed. Install it with your package manager "
        "(e.g. 'sudo dnf install rclone' on Fedora), then click Refresh."
    )
