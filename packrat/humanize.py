"""Human-friendly time and status strings for the UI."""

from __future__ import annotations

import datetime as _dt
from typing import Optional


def describe_past(when: Optional[_dt.datetime], now: Optional[_dt.datetime] = None) -> str:
    """'just now', '5 minutes ago', '3 hours ago', '2 days ago', …"""
    if when is None:
        return "never"
    now = now or _dt.datetime.now()
    seconds = (now - when).total_seconds()
    if seconds < 0:
        seconds = 0
    if seconds < 45:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def describe_future(when: Optional[_dt.datetime], now: Optional[_dt.datetime] = None) -> str:
    """'in 5 minutes', 'tomorrow at 09:00', 'on Monday at 12:00', 'on 3 Jan at 02:00'."""
    if when is None:
        return "not scheduled"
    now = now or _dt.datetime.now()
    seconds = (when - now).total_seconds()
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "any moment now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"in {minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24 and when.date() == now.date():
        return f"today at {when.strftime('%H:%M')}"
    tomorrow = (now + _dt.timedelta(days=1)).date()
    if when.date() == tomorrow:
        return f"tomorrow at {when.strftime('%H:%M')}"
    within_a_week = seconds < 7 * 24 * 3600
    if within_a_week:
        return f"on {when.strftime('%A')} at {when.strftime('%H:%M')}"
    return f"on {when.strftime('%-d %b')} at {when.strftime('%H:%M')}"


def format_snapshot_time(value: str) -> str:
    """'2026-09-28T12:34:56.123456+02:00' -> '28 Sep 2026, 12:34'."""
    if not value:
        return "unknown date"
    try:
        parsed = _dt.datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%-d %b %Y, %H:%M")


def backup_status(
    last_backup: Optional[_dt.datetime],
    scheduled_next: Optional[_dt.datetime],
    paused: bool = False,
    now: Optional[_dt.datetime] = None,
) -> dict:
    """Derive badge state for the overview page.

    Returns {state, label} where state is one of ok / warn / error / idle.
    """
    now = now or _dt.datetime.now()
    if paused:
        return {"state": "idle", "label": "Scheduling paused"}
    if last_backup is None:
        return {"state": "warn", "label": "Not backed up yet"}
    age_hours = (now - last_backup).total_seconds() / 3600
    if scheduled_next is None:
        # No schedule: judge freshness on a 3-day window
        if age_hours <= 72:
            return {"state": "ok", "label": "Backups are up to date"}
        if age_hours <= 24 * 14:
            return {"state": "warn", "label": "Last backup is getting old"}
        return {"state": "error", "label": "Backup overdue"}
    # With a schedule: green until shortly after the next run is due
    if age_hours <= 24:
        return {"state": "ok", "label": "Backups are up to date"}
    if age_hours <= 24 * 7:
        return {"state": "warn", "label": "Missed a scheduled backup"}
    return {"state": "error", "label": "Backup overdue"}


def schedule_summary(mode, time_text: str, weekdays) -> str:
    """Short human sentence for the schedule, e.g. 'Daily at 12:00'."""
    from .settings import ScheduleMode

    if mode is ScheduleMode.OFF:
        return "Manual backups only"
    if mode is ScheduleMode.DAILY:
        return f"Daily at {time_text}"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    picked = ", ".join(names[d] for d in sorted(set(weekdays or [])) if 0 <= d <= 6)
    if picked:
        return f"Weekly on {picked} at {time_text}"
    return f"Weekly at {time_text}"
