import datetime as dt

from packrat.scheduler import _parse_time, next_run_time
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
