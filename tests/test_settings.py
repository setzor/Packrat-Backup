from packrat.settings import Backend, ScheduleMode, Settings, _to_int_list, _to_str_list


def test_defaults_on_fresh_settings(qapp):
    s = Settings()
    assert s.first_run_done is False
    assert s.folders == []
    assert s.schedule.mode is ScheduleMode.OFF
    assert s.backend_cfg.backend is Backend.LOCAL
    assert s.keep_daily == 7


def test_add_remove_folder(qapp):
    s = Settings()
    s.add_folder("/home/user/Documents")
    s.add_folder("/home/user/Documents")
    assert s.folders == ["/home/user/Documents"]
    s.remove_folder("/home/user/Documents")
    assert s.folders == []


def test_backend_summary_local(qapp):
    s = Settings()
    s.backend_cfg.local_path = "/mnt/backup"
    assert s.backend_summary() == "/mnt/backup"


def test_backend_summary_rclone(qapp):
    s = Settings()
    s.backend_cfg.backend = Backend.RCLONE
    s.backend_cfg.rclone_remote = "onedrive"
    s.backend_cfg.rclone_path = "packrat/backups"
    assert s.backend_summary() == "onedrive:packrat/backups"
    assert s.is_backend_configured()


def test_save_and_reload_roundtrip(qapp):
    s = Settings()
    s.folders = ["/data"]
    s.exclude_patterns = ["~/.cache"]
    s.backend_cfg.backend = Backend.RCLONE
    s.backend_cfg.rclone_remote = "gdrive"
    s.backend_cfg.rclone_path = "pack"
    s.schedule.mode = ScheduleMode.WEEKLY
    s.schedule.time = "09:30"
    s.schedule.weekdays = [0, 3]
    s.keep_daily = 3
    s.save()

    s2 = Settings()
    assert s2.folders == ["/data"]
    assert s2.exclude_patterns == ["~/.cache"]
    assert s2.backend_cfg.backend is Backend.RCLONE
    assert s2.backend_cfg.rclone_remote == "gdrive"
    assert s2.backend_cfg.rclone_path == "pack"
    assert s2.schedule.mode is ScheduleMode.WEEKLY
    assert s2.schedule.time == "09:30"
    assert s2.schedule.weekdays == [0, 3]
    assert s2.keep_daily == 3


def test_list_helpers():
    assert _to_str_list("a, b ,,c") == ["a", "b", "c"]
    assert _to_str_list(["x", ""]) == ["x"]
    assert _to_int_list("1, 2, nope") == [1, 2]
