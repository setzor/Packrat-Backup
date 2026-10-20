from packrat.humanize import schedule_summary
from packrat.settings import ScheduleMode, Settings


def test_interval_settings_roundtrip(qapp):
    s = Settings()
    s.schedule.mode = ScheduleMode.INTERVAL
    s.schedule.interval_hours = 48
    s.schedule.interval_start = "03:00"
    s.skip_on_battery = True
    s.skip_on_metered = True
    s.save()
    s2 = Settings()
    assert s2.schedule.mode is ScheduleMode.INTERVAL
    assert s2.schedule.interval_hours == 48
    assert s2.schedule.interval_start == "03:00"
    assert s2.skip_on_battery is True
    assert s2.skip_on_metered is True


def test_interval_settings_defaults(qapp):
    s = Settings()
    assert s.schedule.interval_hours == 6
    assert s.schedule.interval_start == "12:00"
    assert s.skip_on_battery is False
    assert s.skip_on_metered is False


def test_interval_settings_clamps_bad_values(qapp):
    s = Settings()
    s.schedule.interval_hours = 0
    s.save()
    s2 = Settings()
    assert s2.schedule.interval_hours >= 1


def test_schedule_summary_new_modes():
    assert schedule_summary(ScheduleMode.HOURLY, "12:00", []) == "Hourly"
    assert schedule_summary(ScheduleMode.INTERVAL, "12:00", [], interval_hours=6) == "Every 6 hours"
    assert schedule_summary(ScheduleMode.INTERVAL, "12:00", [], interval_hours=48) == "Every 2 day(s)"
    assert schedule_summary(ScheduleMode.INTERVAL, "12:00", []) == "Every 6 hours"
