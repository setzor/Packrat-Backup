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


def test_settings_round_trip_with_commas():
    s = Settings()
    s.folders = ["/home/user/My, Folder", "/home/user/Plain"]
    s.ignored_folders = ["/home/user/other, dir"]
    s.exclude_patterns = ["~/.cache", "**/*,comma*"]
    s.schedule.weekdays = [0, 3]
    s.save()
    s2 = Settings()
    assert s2.folders == ["/home/user/My, Folder", "/home/user/Plain"]
    assert s2.ignored_folders == ["/home/user/other, dir"]
    assert s2.exclude_patterns == ["~/.cache", "**/*,comma*"]
    assert s2.schedule.weekdays == [0, 3]


def test_settings_migrate_legacy_comma_joined():
    s = Settings()
    s._settings.setValue("folders", "/home/a,/home/b")
    s._settings.setValue("exclude_patterns", "~/.cache,~/.local/share/Trash")
    s._settings.setValue("schedule_weekdays", "0,1,2")
    s._load()
    assert s.folders == ["/home/a", "/home/b"]
    assert s.exclude_patterns == ["~/.cache", "~/.local/share/Trash"]
    assert s.schedule.weekdays == [0, 1, 2]
    # Saving migrates to the JSON encoding.
    s.save()
    s2 = Settings()
    assert s2.folders == ["/home/a", "/home/b"]
    assert s2.schedule.weekdays == [0, 1, 2]


def test_settings_decode_garbage_falls_back():
    s = Settings()
    s._settings.setValue("folders", "[broken json")
    s._load()
    assert isinstance(s.folders, list)


def test_settings_decode_empty():
    s = Settings()
    s._settings.setValue("folders", "")
    s._load()
    assert s.folders == []


def test_change_detection_defaults_and_persistence(qapp):
    s = Settings()
    assert s.change_detection is True
    assert s.changed_files_threshold == 35
    assert s.last_change_status == ""
    s.change_detection = False
    s.changed_files_threshold = 60
    s.last_change_status = "suspicious"
    s.save()
    s2 = Settings()
    assert s2.change_detection is False
    assert s2.changed_files_threshold == 60
    assert s2.last_change_status == "suspicious"
