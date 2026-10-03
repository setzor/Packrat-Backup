import datetime as dt

from packrat.scheduler import Scheduler, _parse_time, next_run_time, previous_run_time
from packrat.settings import ScheduleConfig, ScheduleMode


def _cfg(mode, time="12:00", weekdays=(1,)):
    return ScheduleConfig(
        mode=mode,
        time=time,
        weekdays=list(weekdays),
    )


def test_off_mode_never_runs():
    assert next_run_time(_cfg(ScheduleMode.OFF)) is None


def test_daily_future_today():
    now = dt.datetime(2026, 9, 28, 10, 0)
    nxt = next_run_time(_cfg(ScheduleMode.DAILY, "12:00"), now)
    assert nxt == dt.datetime(2026, 9, 28, 12, 0)


def test_daily_next_day_when_past():
    now = dt.datetime(2026, 9, 28, 13, 0)
    nxt = next_run_time(_cfg(ScheduleMode.DAILY, "12:00"), now)
    assert nxt == dt.datetime(2026, 9, 29, 12, 0)


def test_weekly_picks_next_selected_weekday():
    # 2026-09-28 is a Monday (weekday 0); ask for Wednesday (weekday 2)
    now = dt.datetime(2026, 9, 28, 13, 0)
    nxt = next_run_time(_cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[2]), now)
    assert nxt == dt.datetime(2026, 9, 30, 12, 0)
    assert nxt.weekday() == 2


def test_weekly_same_day_but_time_passed():
    # Monday 13:00 with a 12:00 slot on Mondays: next Monday.
    now = dt.datetime(2026, 9, 28, 13, 0)
    nxt = next_run_time(_cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[0]), now)
    assert nxt == dt.datetime(2026, 10, 5, 12, 0)


def test_weekly_same_day_time_still_ahead():
    now = dt.datetime(2026, 9, 28, 9, 0)
    nxt = next_run_time(_cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[0]), now)
    assert nxt == dt.datetime(2026, 9, 28, 12, 0)


def test_parse_time_clamps_and_defaults():
    assert _parse_time("99:99") == (23, 59)
    assert _parse_time("not-a-time") == (12, 0)
    assert _parse_time("03:07") == (3, 7)


def test_previous_run_time_daily():
    now = dt.datetime(2026, 9, 28, 15, 0)
    prev = previous_run_time(_cfg(ScheduleMode.DAILY, "12:00"), now)
    assert prev == dt.datetime(2026, 9, 28, 12, 0)
    now = dt.datetime(2026, 9, 28, 9, 0)
    prev = previous_run_time(_cfg(ScheduleMode.DAILY, "12:00"), now)
    assert prev == dt.datetime(2026, 9, 27, 12, 0)


def test_previous_run_time_weekly():
    # Monday 09:00 with Monday 12:00 slots: previous slot is last Monday.
    now = dt.datetime(2026, 9, 28, 9, 0)
    prev = previous_run_time(_cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[0]), now)
    assert prev == dt.datetime(2026, 9, 21, 12, 0)
    # Later that Monday: previous slot is today.
    now = dt.datetime(2026, 9, 28, 15, 0)
    prev = previous_run_time(_cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[0]), now)
    assert prev == dt.datetime(2026, 9, 28, 12, 0)


def test_previous_run_time_off_is_none():
    assert previous_run_time(_cfg(ScheduleMode.OFF, "12:00")) is None


def test_scheduler_missed_backup_detection(qapp):
    cfg = _cfg(ScheduleMode.DAILY, "12:00")
    s = Scheduler(cfg)
    s.recompute()
    now = dt.datetime(2026, 9, 28, 15, 0)
    # Last backup before today's slot: missed.
    assert s.missed_backup(dt.datetime(2026, 9, 28, 8, 0), now)
    # Last backup after today's slot: not missed.
    assert not s.missed_backup(dt.datetime(2026, 9, 28, 12, 30), now)
    # Never backed up: no catch-up (let the regular schedule run).
    assert not s.missed_backup(None, now)
    # Paused or off: no catch-up.
    s.set_paused(True)
    assert not s.missed_backup(dt.datetime(2026, 9, 28, 8, 0), now)
    s.set_paused(False)
    s.config().mode = ScheduleMode.OFF
    assert not s.missed_backup(dt.datetime(2026, 9, 28, 8, 0), now)


def test_previous_run_time_weekly_after_long_absence():
    # Issue #44: Packrat not running for weeks must still find the missed slot.
    # Thu 8 Oct 2026, Monday 12:00 slots, last run 5 weeks ago.
    now = dt.datetime(2026, 10, 8, 10, 0)
    cfg = _cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[0])
    prev = previous_run_time(cfg, now)
    assert prev == dt.datetime(2026, 10, 5, 12, 0)
    s = Scheduler(cfg)
    assert s.missed_backup(dt.datetime(2026, 9, 2, 12, 0), now)
    # Same even after a very long absence (years).
    assert s.missed_backup(dt.datetime(2023, 10, 8, 12, 0), now)


def test_previous_run_time_weekly_invalid_weekdays_is_none():
    # Corrupted/hand-edited settings must not silently fall back to Monday.
    cfg = _cfg(ScheduleMode.WEEKLY, "12:00", weekdays=[7, 8])
    assert previous_run_time(cfg, dt.datetime(2026, 10, 8, 10, 0)) is None
    assert next_run_time(cfg, dt.datetime(2026, 10, 8, 10, 0)) is None
