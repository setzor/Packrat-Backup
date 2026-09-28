"""Desktop notifications with a log-printing fallback for headless runs."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_ICON = "org.packrat.Backup"


def notify(title: str, body: str, urgency: str = "normal") -> None:
    """Send a desktop notification, best effort."""
    urgency_args = []
    if urgency == "critical":
        urgency_args = ["-u", "critical"]
    try:
        import subprocess

        subprocess.run(
            ["notify-send", "-a", "Packrat Backup", "-i", _ICON] + urgency_args + [title, body],
            check=False,
            timeout=5,
        )
    except Exception as exc:
        log.debug("notify-send failed: %s", exc)


def notify_error(title: str, body: str) -> None:
    notify(title, body, urgency="critical")
