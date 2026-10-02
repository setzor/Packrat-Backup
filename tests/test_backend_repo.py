import pytest

from packrat.backend import BackendError, BackupBackend
from packrat.restic import ResticRunner
from packrat.settings import Backend, Settings


def _rclone_settings(remote="myremote", path="packrat-backups"):
    settings = Settings()
    settings.backend_cfg.backend = Backend.RCLONE
    settings.backend_cfg.rclone_remote = remote
    settings.backend_cfg.rclone_path = path
    settings.folders = ["/tmp/packrat-test-home/source"]
    return settings


@pytest.fixture()
def backend(qapp):
    return BackupBackend(_rclone_settings())


def test_rclone_repo_location_is_valid(backend):
    assert backend.repo_location() == "rclone:myremote:packrat-backups"


def test_rclone_repo_location_normalises_slashes(qapp):
    settings = _rclone_settings(path="/packrat-backups/")
    backend = BackupBackend(settings)
    assert backend.repo_location() == "rclone:myremote:packrat-backups"


def test_rclone_repo_location_rejects_empty_path(qapp):
    settings = _rclone_settings(path="")
    backend = BackupBackend(settings)
    with pytest.raises(BackendError):
        backend.repo_location()


def test_rclone_repo_location_rejects_slashes_only_path(qapp):
    settings = _rclone_settings(path="/")
    backend = BackupBackend(settings)
    with pytest.raises(BackendError):
        backend.repo_location()


def test_run_backup_probes_instead_of_local_only_check(backend, monkeypatch, tmp_path):
    calls = []

    def fake_run(args, timeout=300, password=""):
        calls.append(list(args))
        return False, "", "Fatal: repository does not exist"

    monkeypatch.setattr("packrat.backend.Restic.run", fake_run)
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: None)
    backend.run_backup()
    assert calls == [["--repo", "rclone:myremote:packrat-backups", "cat", "config"]]
    assert backend._initing_for_backup is True


def test_repo_exists_true_when_config_probe_succeeds(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run", lambda args, timeout=300, password="": (True, "{}", "")
    )
    assert backend._repo_exists() is True


def test_repo_exists_false_on_exit_code_missing_message(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="": (False, "", "Fatal: repository does not exist"),
    )
    assert backend._repo_exists() is False


def test_repo_exists_true_on_wrong_password(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="": (
            False,
            "",
            "Fatal: wrong password or no key found",
        ),
    )
    assert backend._repo_exists() is True


def test_repo_exists_false_on_other_rclone_error(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="": (False, "", "some other failure"),
    )
    assert backend._repo_exists() is False


def test_run_backup_backs_up_when_remote_repo_exists(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run", lambda args, timeout=300, password="": (True, "{}", "")
    )
    launched = []
    monkeypatch.setattr(
        ResticRunner,
        "backup",
        lambda self, repo, password, folders, excludes: launched.append(repo),
    )
    backend.run_backup()
    assert launched == ["rclone:myremote:packrat-backups"]
    assert backend._initing_for_backup is False


def test_run_backup_falls_back_to_local_keys_check(backend, monkeypatch):
    def failing_run(args, timeout=300, password=""):
        raise FileNotFoundError("restic binary vanished")

    monkeypatch.setattr("packrat.backend.Restic.run", failing_run)
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: None)
    assert backend._repo_exists() is False


def test_repo_probe_passes_password(backend, monkeypatch):
    seen = {}

    def fake_run(args, timeout=300, password=""):
        seen["args"] = list(args)
        seen["password"] = password
        return True, "{}", ""

    monkeypatch.setattr("packrat.backend.Restic.run", fake_run)
    backend.set_password("s3cret")
    assert backend._repo_exists() is True
    assert seen["args"] == ["--repo", "rclone:myremote:packrat-backups", "cat", "config"]
    assert seen["password"] == "s3cret"


def test_repo_exists_false_on_legacy_missing_repo_wording(backend, monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="": (
            False,
            "",
            "Fatal: unable to open config file: stat /x/config: no such file or directory",
        ),
    )
    assert backend._repo_exists() is False
