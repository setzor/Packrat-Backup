import datetime as dt

from packrat.scheduler import Scheduler, next_run_time, previous_run_time
from packrat.settings import ScheduleConfig, ScheduleMode


def _cfg(mode, interval_hours=6, interval_start="12:00", **kw):
    return ScheduleConfig(
        mode=mode,
        interval_hours=interval_hours,
        interval_start=interval_start,
        **kw,
    )


def test_hourly_next_run():
    now = dt.datetime(2026, 10, 12, 10, 15)
    nxt = next_run_time(_cfg(ScheduleMode.HOURLY), now)
    assert nxt == dt.datetime(2026, 10, 12, 11, 0)


def test_hourly_next_run_on_the_hour():
    now = dt.datetime(2026, 10, 12, 10, 0)
    nxt = next_run_time(_cfg(ScheduleMode.HOURLY), now)
    assert nxt == dt.datetime(2026, 10, 12, 11, 0)


def test_hourly_previous_run():
    now = dt.datetime(2026, 10, 12, 10, 15)
    prev = previous_run_time(_cfg(ScheduleMode.HOURLY), now)
    assert prev == dt.datetime(2026, 10, 12, 10, 0)


def test_interval_next_run_future_today():
    now = dt.datetime(2026, 10, 12, 8, 0)
    nxt = next_run_time(_cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00"), now)
    assert nxt == dt.datetime(2026, 10, 12, 12, 0)


def test_interval_next_run_rolls_forward():
    # 12:00 anchor, every 6 hours: 12, 18, 0, 6, 12...
    now = dt.datetime(2026, 10, 12, 13, 0)
    nxt = next_run_time(_cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00"), now)
    assert nxt == dt.datetime(2026, 10, 12, 18, 0)


def test_interval_next_run_across_days():
    now = dt.datetime(2026, 10, 12, 23, 30)
    nxt = next_run_time(_cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00"), now)
    assert nxt == dt.datetime(2026, 10, 13, 0, 0)


def test_interval_daily_hours():
    now = dt.datetime(2026, 10, 12, 13, 0)
    nxt = next_run_time(_cfg(ScheduleMode.INTERVAL, interval_hours=48, interval_start="12:00"), now)
    assert nxt == dt.datetime(2026, 10, 14, 12, 0)


def test_interval_previous_run():
    now = dt.datetime(2026, 10, 12, 13, 0)
    prev = previous_run_time(
        _cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00"), now
    )
    assert prev == dt.datetime(2026, 10, 12, 12, 0)


def test_interval_previous_run_before_anchor():
    now = dt.datetime(2026, 10, 12, 9, 0)
    prev = previous_run_time(
        _cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00"), now
    )
    assert prev == dt.datetime(2026, 10, 12, 6, 0)


def test_interval_invalid_hours_falls_back():
    now = dt.datetime(2026, 10, 12, 13, 0)
    cfg = _cfg(ScheduleMode.INTERVAL, interval_hours=0)
    nxt = next_run_time(cfg, now)
    # Zero/garbage interval falls back to 6 hours from the 12:00 anchor.
    assert nxt == dt.datetime(2026, 10, 12, 18, 0)


def test_interval_missed_backup():
    cfg = _cfg(ScheduleMode.INTERVAL, interval_hours=6, interval_start="12:00")
    s = Scheduler(cfg)
    now = dt.datetime(2026, 10, 12, 13, 0)
    assert s.missed_backup(dt.datetime(2026, 10, 12, 11, 0), now)
    assert not s.missed_backup(dt.datetime(2026, 10, 12, 12, 30), now)


def test_scheduler_guard_defer_and_fire(qapp, monkeypatch):
    cfg = _cfg(ScheduleMode.DAILY, "12:00")
    s = Scheduler(cfg)
    monkeypatch.setattr(
        "packrat.scheduler.check_guards",
        lambda b, m: __import__("packrat.guards", fromlist=["GuardBlock"]).GuardBlock("battery"),
    )
    s.recompute()
    # Force the slot to be due.
    s._next_run = dt.datetime.now() - dt.timedelta(minutes=1)
    fired = []
    deferred = []
    s.backup_due.connect(lambda: fired.append(True))
    s.deferred_changed.connect(lambda on: deferred.append(on))
    s._on_tick()
    assert fired == []
    assert s.is_deferred()
    assert deferred == [True]

    monkeypatch.setattr("packrat.scheduler.check_guards", lambda b, m: None)
    s._on_tick()
    assert fired == [True]
    assert not s.is_deferred()
    assert deferred == [True, False]


def test_scheduler_busy_check_defers(qapp, monkeypatch):
    cfg = _cfg(ScheduleMode.DAILY, "12:00")
    s = Scheduler(cfg)
    monkeypatch.setattr("packrat.scheduler.check_guards", lambda b, m: None)
    s.set_busy_check(lambda: True)
    s.recompute()
    s._next_run = dt.datetime.now() - dt.timedelta(minutes=1)
    fired = []
    s.backup_due.connect(lambda: fired.append(True))
    s._on_tick()
    assert fired == []
    assert s.is_deferred()
    s.set_busy_check(lambda: False)
    s._on_tick()
    assert fired == [True]


def test_scheduler_guards_disabled_run_normally(qapp, monkeypatch):
    calls = []

    def fake_check(battery, metered):
        calls.append((battery, metered))
        return None

    monkeypatch.setattr("packrat.scheduler.check_guards", fake_check)
    cfg = _cfg(ScheduleMode.DAILY, "12:00")
    s = Scheduler(cfg)
    s.set_guards(True, True)
    s.recompute()
    s._next_run = dt.datetime.now() - dt.timedelta(minutes=1)
    fired = []
    s.backup_due.connect(lambda: fired.append(True))
    s._on_tick()
    assert fired == [True]
    assert calls == [(True, True)]
