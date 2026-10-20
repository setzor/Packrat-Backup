"""Power and network guards for scheduled backups.

Queries the standard desktop services, best effort with subprocesses so
there is no hard D-Bus dependency and no extra Python packages:
- battery state via UPower (``upower`` CLI) or logind
- metered connections via NetworkManager (``nmcli``)

Every check degrades to "not blocked" when the tool is missing or the
output cannot be parsed, so guards never prevent backups on unusual
setups.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

_TIMEOUT = 5


class GuardBlock:
    """Why a scheduled backup is being deferred."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.reason} ({self.detail})"
        return self.reason


def _run(cmd: list) -> Optional[str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout or ""


def on_battery() -> bool:
    """True when the machine is running on battery power."""
    state = _run(["upower", "-i", "/org/freedesktop/UPower/devices/line_power_AC"])
    if state is not None and "online: yes" in state:
        return False
    dump = _run(["upower", "-d"])
    if dump is not None:
        for line in dump.splitlines():
            if line.strip().startswith("on-battery:"):
                if "yes" in line.lower():
                    return True
                return False
    status = _run(["cat", "/sys/class/power_supply/A*/online"])
    if status is not None:
        flags = [ln.strip() for ln in status.splitlines() if ln.strip()]
        if flags and all(ln == "0" for ln in flags):
            return True
        if flags:
            return False
    logind = _run(["systemctl", "show", "org.freedesktop.login1", "--property=OnExternalPower"])
    if logind is not None:
        return "OnExternalPower=no" in logind
    return False


def on_metered_connection() -> bool:
    """True when the active network connection is metered."""
    out = _run(["nmcli", "-t", "-f", "GENERAL.CONNECTION-METERED", "device", "status"])
    if out is None:
        return False
    for line in out.splitlines():
        if line.strip().endswith("yes"):
            return True
    return False


def check_guards(skip_on_battery: bool, skip_on_metered: bool) -> Optional[GuardBlock]:
    """Return why a scheduled backup should be deferred, or None to run it."""
    if skip_on_battery and on_battery():
        return GuardBlock("deferring: running on battery", "on battery power")
    if skip_on_metered and on_metered_connection():
        return GuardBlock("deferring: metered network connection", "metered connection")
    return None
