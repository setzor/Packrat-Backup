import datetime as dt

from packrat.humanize import (
    backup_status,
    describe_future,
    describe_past,
    format_snapshot_time,
    schedule_summary,
)
from packrat.settings import ScheduleMode

NOW = dt.datetime(2026, 9, 28, 12, 0)


def test_describe_past():
    assert describe_past(None) == "never"
    assert describe_past(NOW, NOW) == "just now"
    assert describe_past(NOW - dt.timedelta(minutes=5), NOW) == "5 minutes ago"
    assert describe_past(NOW - dt.timedelta(minutes=1), NOW) == "1 minute ago"
    assert describe_past(NOW - dt.timedelta(hours=3), NOW) == "3 hours ago"
    assert describe_past(NOW - dt.timedelta(days=2), NOW) == "2 days ago"
    assert describe_past(NOW - dt.timedelta(days=14), NOW) == "2 weeks ago"
    assert describe_past(NOW - dt.timedelta(days=70), NOW) == "2 months ago"


def test_describe_future():
    assert describe_future(None) == "not scheduled"
    assert describe_future(NOW, NOW) == "any moment now"
    assert describe_future(NOW + dt.timedelta(minutes=30), NOW) == "in 30 minutes"
    assert describe_future(NOW + dt.timedelta(hours=5), NOW) == "today at 17:00"
    assert describe_future(NOW + dt.timedelta(days=1, hours=2), NOW) == "tomorrow at 14:00"
    assert describe_future(NOW + dt.timedelta(days=3), NOW) == "on Thursday at 12:00"


def test_format_snapshot_time():
    assert format_snapshot_time("") == "unknown date"
    text = format_snapshot_time("2026-09-28T12:34:56.123456+02:00")
    assert text == "28 Sep 2026, 12:34"


def test_backup_status_states():
    # never backed up
    status = backup_status(None, None)
    assert status == {"state": "warn", "label": "Not backed up yet"}
    # paused
    status = backup_status(NOW, None, paused=True)
    assert status["state"] == "idle"
    assert "paused" in status["label"]
    # fresh backup, no schedule
    status = backup_status(NOW - dt.timedelta(hours=2), None, now=NOW)
    assert status["state"] == "ok"
    # old backup, no schedule
    status = backup_status(NOW - dt.timedelta(days=5), None, now=NOW)
    assert status["state"] == "warn"
    status = backup_status(NOW - dt.timedelta(days=30), None, now=NOW)
    assert status["state"] == "error"
    # with schedule: recent backup is green
    status = backup_status(NOW - dt.timedelta(hours=3), NOW, now=NOW)
    assert status["state"] == "ok"
    # missed scheduled run
    status = backup_status(NOW - dt.timedelta(days=2), NOW, now=NOW)
    assert status["state"] == "warn"


def test_schedule_summary():
    assert schedule_summary(ScheduleMode.OFF, "12:00", []) == "Manual backups only"
    assert schedule_summary(ScheduleMode.DAILY, "09:00", []) == "Daily at 09:00"
    text = schedule_summary(ScheduleMode.WEEKLY, "12:00", [0, 2])
    assert text == "Weekly on Mon, Wed at 12:00"


def test_restore_folders_text(qapp):
    import os

    from packrat.pages.restore import _folders_text

    home = os.path.expanduser("~")
    snap = {"paths": [home, home + "/Documents", "/srv/data"]}
    text = _folders_text(snap)
    assert "~" in text
    assert "~/Documents" in text
    assert "/srv/data" in text

    many = {"paths": [f"/folder{i}" for i in range(6)]}
    text = _folders_text(many)
    assert "(+2 more)" in text

    assert _folders_text({}) == "unknown"
