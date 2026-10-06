from packrat.settings import ScheduleConfig, ScheduleMode


def test_load_does_not_emit_changed_or_corrupt_config(qapp):
    from packrat.pages.schedule import SchedulePage

    cfg = ScheduleConfig(mode=ScheduleMode.WEEKLY, time="05:00", weekdays=[6])
    page = SchedulePage()
    saved = []
    page.changed.connect(lambda: saved.append(page.save()))
    page.load(cfg)
    assert saved == []
    assert cfg.time == "05:00"
    assert cfg.weekdays == [6]


def test_load_survives_live_save_wiring(qapp):
    from packrat.pages.schedule import SchedulePage

    cfg = ScheduleConfig(mode=ScheduleMode.WEEKLY, time="05:00", weekdays=[6])
    page = SchedulePage()

    def save_like_main():
        data = page.save()
        cfg.mode = data["mode"]
        cfg.time = data["time"]
        cfg.weekdays = data["weekdays"]

    page.changed.connect(save_like_main)
    page.load(cfg)
    assert cfg.mode is ScheduleMode.WEEKLY
    assert cfg.time == "05:00"
    assert cfg.weekdays == [6]

    check, value = page._day_checks[5]
    check.setChecked(True)
    assert cfg.weekdays == [5, 6]
    assert page.save()["time"] == "05:00"


def test_pause_checkbox_roundtrip_and_greys_out_schedule(qapp):
    from packrat.pages.schedule import SchedulePage

    cfg = ScheduleConfig(mode=ScheduleMode.WEEKLY, time="05:00", weekdays=[6])
    page = SchedulePage()
    page.load(cfg)
    assert page.save()["paused"] is False

    page._pause_check.setChecked(True)
    assert page.save()["paused"] is True
    assert not page._daily_radio.isEnabled()
    assert not page._time_combo.isEnabled()
    check, _value = page._day_checks[5]
    assert not check.isEnabled()
    # Schedule config itself is untouched while paused.
    assert page.save()["mode"] is ScheduleMode.WEEKLY
    assert page.save()["time"] == "05:00"

    page._pause_check.setChecked(False)
    assert page._daily_radio.isEnabled()
    assert page._time_combo.isEnabled()
    assert check.isEnabled()


def test_pause_load_reflects_saved_state(qapp):
    from packrat.pages.schedule import SchedulePage

    cfg = ScheduleConfig(mode=ScheduleMode.DAILY, time="05:00")
    page = SchedulePage()
    page.load(cfg, paused=True)
    assert page._pause_check.isChecked()
    assert not page._daily_radio.isEnabled()
    page.load(cfg, paused=False)
    assert not page._pause_check.isChecked()
    assert page._daily_radio.isEnabled()


def test_retention_roundtrip_and_auto_prune_setting(qapp):
    from packrat.pages.schedule import SchedulePage
    from packrat.settings import Settings

    cfg = ScheduleConfig(mode=ScheduleMode.DAILY, time="12:00")
    page = SchedulePage()
    settings = Settings()
    settings.keep_daily = 14
    settings.keep_weekly = 6
    settings.keep_monthly = 3
    settings.keep_yearly = 1
    settings.auto_prune = False
    page.load(cfg, settings=settings)
    data = page.save()
    assert data["keep_daily"] == 14
    assert data["keep_weekly"] == 6
    assert data["keep_monthly"] == 3
    assert data["keep_yearly"] == 1
    assert data["auto_prune"] is False

    page._auto_prune_check.setChecked(True)
    page._keep_daily_spin.setValue(7)
    page._auto_prune_interval_spin.setValue(30)
    data = page.save()
    assert data["auto_prune"] is True
    assert data["keep_daily"] == 7
    assert data["auto_prune_interval_days"] == 30


def test_pause_does_not_grey_out_retention(qapp):
    from packrat.pages.schedule import SchedulePage
    from packrat.settings import ScheduleConfig, ScheduleMode

    cfg = ScheduleConfig(mode=ScheduleMode.DAILY, time="12:00")
    page = SchedulePage()
    page.load(cfg)
    page._pause_check.setChecked(True)
    assert page._keep_daily_spin.isEnabled()
    assert page._auto_prune_check.isEnabled()
    assert page._clean_now_button.isEnabled()


def test_clean_now_button_emits_signal(qapp):
    from packrat.pages.schedule import SchedulePage

    page = SchedulePage()
    fired = []
    page.clean_now_requested.connect(lambda: fired.append(True))
    page._clean_now_button.click()
    assert fired == [True]
