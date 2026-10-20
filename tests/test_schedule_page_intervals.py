from packrat.pages.schedule import SchedulePage
from packrat.settings import ScheduleConfig, ScheduleMode, Settings


def _cfg(**kw):
    return ScheduleConfig(**kw)


def test_hourly_roundtrip(qapp):
    cfg = _cfg(mode=ScheduleMode.HOURLY)
    page = SchedulePage()
    saved = []
    page.changed.connect(lambda: saved.append(page.save()))
    page.load(cfg)
    assert saved == []
    assert page.save()["mode"] is ScheduleMode.HOURLY
    assert page._hourly_radio.isChecked()
    assert not page._interval_spin.isEnabled()


def test_interval_roundtrip_hours(qapp):
    cfg = _cfg(mode=ScheduleMode.INTERVAL, interval_hours=6, interval_start="09:00")
    page = SchedulePage()
    page.load(cfg)
    data = page.save()
    assert data["mode"] is ScheduleMode.INTERVAL
    assert data["interval_hours"] == 6
    assert data["interval_start"] == "09:00"
    assert page._interval_spin.isEnabled()
    assert page._interval_start_combo.isEnabled()


def test_interval_days_roundtrip(qapp):
    cfg = _cfg(mode=ScheduleMode.INTERVAL, interval_hours=48)
    page = SchedulePage()
    page.load(cfg)
    assert page._interval_unit.currentText() == "days"
    data = page.save()
    assert data["interval_hours"] == 48


def test_interval_unit_switch_updates_suffix_and_range(qapp):
    cfg = _cfg(mode=ScheduleMode.INTERVAL, interval_hours=6)
    page = SchedulePage()
    page.load(cfg)
    page._interval_unit.setCurrentIndex(1)
    assert page._interval_spin.suffix() == " days"
    page._interval_spin.setValue(2)
    page._interval_unit.setCurrentIndex(0)
    assert page._interval_spin.suffix() == " hours"
    assert page.save()["interval_hours"] == 2


def test_guards_roundtrip(qapp):
    cfg = _cfg(mode=ScheduleMode.DAILY)
    settings = Settings()
    settings.skip_on_battery = True
    settings.skip_on_metered = True
    page = SchedulePage()
    page.load(cfg, settings=settings)
    assert page.save()["skip_on_battery"] is True
    assert page.save()["skip_on_metered"] is True
    page._battery_check.setChecked(False)
    page._metered_check.setChecked(False)
    assert page.save()["skip_on_battery"] is False
    assert page.save()["skip_on_metered"] is False


def test_guards_default_off(qapp):
    cfg = _cfg(mode=ScheduleMode.DAILY)
    page = SchedulePage()
    page.load(cfg)
    data = page.save()
    assert data["skip_on_battery"] is False
    assert data["skip_on_metered"] is False


def test_interval_widgets_greyed_out_when_paused(qapp):
    cfg = _cfg(mode=ScheduleMode.INTERVAL, interval_hours=6)
    page = SchedulePage()
    page.load(cfg)
    page._pause_check.setChecked(True)
    assert not page._interval_spin.isEnabled()
    assert not page._interval_start_combo.isEnabled()
    page._pause_check.setChecked(False)
    assert page._interval_spin.isEnabled()
