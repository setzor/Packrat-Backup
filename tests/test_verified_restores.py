from packrat.backend import BackupBackend
from packrat.settings import Backend, Settings


def _backend(qapp, mode="sample"):
    s = Settings()
    s.backend_cfg.backend = Backend.LOCAL
    s.backend_cfg.local_path = "/tmp/does-not-matter"
    s.verify_after_backup = mode
    return BackupBackend(s), s


def test_settings_verify_defaults_and_persistence(qapp):
    s = Settings()
    assert s.verify_after_backup == "sample"
    assert s.last_verified_time == ""
    assert s.last_verified_ok is False
    s.verify_after_backup = "full"
    s.last_verified_time = "2026-10-03T12:00:00"
    s.last_verified_ok = True
    s.save()
    s2 = Settings()
    assert s2.verify_after_backup == "full"
    assert s2.last_verified_time == "2026-10-03T12:00:00"
    assert s2.last_verified_ok is True


def test_settings_verify_invalid_value_falls_back(qapp):
    s = Settings()
    s._settings.setValue("verify_after_backup", "bogus")
    s._load()
    assert s.verify_after_backup == "sample"


def test_backend_verify_backup_launches_check(qapp, monkeypatch):
    backend, _ = _backend(qapp)
    launched = []
    monkeypatch.setattr(
        backend.restic,
        "verify",
        lambda repo, password, read_data="sample": launched.append((repo, read_data)),
    )
    backend.verify_backup()
    assert launched == [("/tmp/does-not-matter", "sample")]


def test_backend_verify_backup_skipped_when_off(qapp, monkeypatch):
    backend, _ = _backend(qapp, mode="off")
    launched = []
    monkeypatch.setattr(backend.restic, "verify", lambda *a, **k: launched.append(1))
    backend.verify_backup()
    assert launched == []


def test_backend_verify_finished_signal(qapp):
    backend, _ = _backend(qapp)
    results = []
    backend.verify_finished.connect(lambda ok, msg: results.append((ok, msg)))
    backend._on_restic_finished(True, "no errors were found")  # default op path
    # emulate a verify operation
    backend.restic._operation = "verify"
    backend._on_restic_finished(True, "no errors were found")
    assert results == [(True, "no errors were found")]


def test_restic_check_args(qapp):
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    assert runner._check_args("off") == ["check"]
    assert runner._check_args("sample") == ["check", "--read-data-subset=10%"]
    assert runner._check_args("full") == ["check", "--read-data"]
