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
