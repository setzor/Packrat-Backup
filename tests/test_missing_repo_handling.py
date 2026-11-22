"""Friendly handling when the backup repository does not exist yet.

Regression tests for the raw restic exit-10 JSON blob ("repository does not
exist") that used to surface as a modal dialog on "Estimate Next Backup" and
on the Restore page when no backup had ever been made, or after the cloud
backups were deleted manually. The preview now creates the repository first
and still estimates; the restore page shows an inline notice instead.
"""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QMessageBox

from packrat.backend import BackupBackend
from packrat.main import MainWindow
from packrat.pages.restore import RestorePage
from packrat.restic import ResticRunner, _result_message, is_repo_missing, repo_missing_message
from packrat.settings import Backend, Settings

EXIT10_STDERR = (
    '{"message_type":"exit_error","code":10,"message":"Fatal: repository does not exist: '
    "unable to open config file: <config/> does not exist\\nIs there a repository at the "
    'following location?\\nrclone:google-drive:packrat-backups"}\n'
)


def _rclone_settings(remote="google-drive", path="packrat-backups"):
    settings = Settings()
    settings.backend_cfg.backend = Backend.RCLONE
    settings.backend_cfg.rclone_remote = remote
    settings.backend_cfg.rclone_path = path
    settings.folders = ["/tmp/packrat-test-home/source"]
    return settings


# ------------------------------------------------------------- restic layer
def test_is_repo_missing_matches_exit10_json():
    assert is_repo_missing(EXIT10_STDERR)


def test_is_repo_missing_matches_legacy_wording():
    assert is_repo_missing(
        "Fatal: unable to open config file: stat /x/config: no such file or directory"
    )
    assert is_repo_missing(
        "Is there a repository at the following location?\nrclone:google-drive:packrat-backups"
    )


def test_is_repo_missing_matches_friendly_message():
    assert is_repo_missing(repo_missing_message("rclone:google-drive:packrat-backups"))


def test_is_repo_missing_ignores_other_errors():
    assert not is_repo_missing("Fatal: wrong password or no key found")
    assert not is_repo_missing("connection reset by peer")
    assert not is_repo_missing("")


def test_result_message_repo_missing_is_friendly():
    msg = _result_message(
        "snapshots", False, 10, EXIT10_STDERR, repo="rclone:google-drive:packrat-backups"
    )
    assert msg == repo_missing_message("rclone:google-drive:packrat-backups")
    assert "rclone:google-drive:packrat-backups" in msg
    assert "{" not in msg
    assert "exit_error" not in msg


def test_result_message_repo_missing_without_repo():
    assert _result_message("dry-run", False, 10, EXIT10_STDERR) == repo_missing_message("")


def test_result_message_other_failures_unchanged():
    msg = _result_message(
        "backup", False, 1, "Fatal: wrong password or no key found", repo="rclone:x:y"
    )
    assert msg.startswith("Backup complete failed (exit 1)")
    assert "wrong password" in msg


def test_result_message_success_unchanged():
    assert _result_message("snapshots", True, 0, "", repo="rclone:x:y") == "Snapshots listed"


# ------------------------------------------------------------- backend layer
@pytest.fixture()
def backend(qapp):
    return BackupBackend(_rclone_settings())


def _missing_repo_probe(monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="", options=None: (
            False,
            "",
            "Fatal: repository does not exist",
        ),
    )


def _existing_repo_probe(monkeypatch):
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="", options=None: (True, "{}", ""),
    )


def _capture_backup(monkeypatch):
    launched = []

    def fake_backup(self, repo, password, folders, excludes, dry_run=False, options=None):
        launched.append({"repo": repo, "dry_run": dry_run})

    monkeypatch.setattr(ResticRunner, "backup", fake_backup)
    return launched


def test_preview_backup_inits_missing_repo_then_dry_runs(backend, monkeypatch):
    _missing_repo_probe(monkeypatch)
    launched = _capture_backup(monkeypatch)
    inited = []
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: inited.append(a))

    backend.preview_backup()
    assert len(inited) == 1
    assert backend._initing_for_preview is True
    assert launched == []

    backend.restic._operation = "init"
    backend._on_restic_finished(True, "Repository initialised")
    assert launched == [{"repo": "rclone:google-drive:packrat-backups", "dry_run": True}]
    assert backend._initing_for_preview is False


def test_preview_backup_init_failure_reports_dry_run_error(backend, monkeypatch):
    _missing_repo_probe(monkeypatch)
    _capture_backup(monkeypatch)
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: None)
    events = []
    backend.operation_finished.connect(lambda op, ok, msg: events.append((op, ok, msg)))

    backend.preview_backup()
    backend.restic._operation = "init"
    backend._on_restic_finished(False, "init failed: network unreachable")
    assert events == [("dry-run", False, "init failed: network unreachable")]
    assert backend._initing_for_preview is False


def test_preview_backup_runs_dry_run_directly_when_repo_exists(backend, monkeypatch):
    _existing_repo_probe(monkeypatch)
    launched = _capture_backup(monkeypatch)
    inited = []
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: inited.append(a))

    backend.preview_backup()
    assert launched == [{"repo": "rclone:google-drive:packrat-backups", "dry_run": True}]
    assert inited == []
    assert backend._initing_for_preview is False


def test_run_backup_still_chains_real_backup_after_init(backend, monkeypatch):
    _missing_repo_probe(monkeypatch)
    launched = _capture_backup(monkeypatch)
    monkeypatch.setattr(backend.restic, "init", lambda *a, **k: None)

    backend.run_backup()
    assert backend._initing_for_backup is True
    backend.restic._operation = "init"
    backend._on_restic_finished(True, "Repository initialised")
    assert launched == [{"repo": "rclone:google-drive:packrat-backups", "dry_run": False}]
    assert backend._initing_for_backup is False


# ------------------------------------------------------------- UI layer
@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = _rclone_settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    win = MainWindow(settings)
    win.backend.set_password("test-password")
    yield win
    win.tray.hide()
    win.close()


def _warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(str(a))))
    return calls


def test_start_preview_creates_repo_before_estimating(window, monkeypatch):
    _missing_repo_probe(monkeypatch)
    ops = []
    monkeypatch.setattr(window.backend.restic, "init", lambda *a, **k: ops.append("init"))
    monkeypatch.setattr(
        ResticRunner,
        "backup",
        lambda self, repo, password, folders, excludes, dry_run=False, options=None: ops.append(
            ("backup", dry_run)
        ),
    )

    window.start_preview()
    assert ops == ["init"]
    assert window.overview_page._preview_button.text() == "Estimating…"

    window.backend.restic._operation = "init"
    window.backend._on_restic_finished(True, "Repository initialised")
    assert ops == ["init", ("backup", True)]


def test_snapshots_failure_repo_missing_shows_friendly_notice(window, monkeypatch):
    warnings = _warnings(monkeypatch)
    window.restore_page.set_loading(True)

    window._on_operation_finished(
        "snapshots", False, repo_missing_message(window.backend.repo_location())
    )

    assert warnings == []
    assert window.restore_page._table.rowCount() == 0
    assert not window.restore_page._loading_label.isVisibleTo(window.restore_page)
    notice = window.restore_page._notice_label.text()
    assert window.restore_page._notice_label.isVisibleTo(window.restore_page)
    assert "nothing to restore" in notice.lower()
    assert "rclone:google-drive:packrat-backups" in notice
    assert "Storage page" in notice


def test_snapshots_failure_other_error_shows_single_modal(window, monkeypatch):
    warnings = _warnings(monkeypatch)

    window._on_operation_finished("snapshots", False, "Snapshots listed failed (exit 1): boom")

    assert len(warnings) == 1
    assert "Could not list snapshots" in warnings[0]
    assert not window.restore_page._notice_label.isVisibleTo(window.restore_page)


def test_job_finished_does_not_double_modal_for_handled_operations(window, monkeypatch):
    warnings = _warnings(monkeypatch)

    window.job.last_operation = "dry-run"
    window._on_job_finished(False, "Backup preview complete failed (exit 10): {...}")
    window.job.last_operation = "snapshots"
    window._on_job_finished(False, repo_missing_message("rclone:google-drive:packrat-backups"))
    window.job.last_operation = "ls"
    window._on_job_finished(False, "Snapshot contents listed failed (exit 10): {...}")
    assert warnings == []

    window.job.last_operation = "backup"
    window._on_job_finished(False, "Backup complete failed (exit 1): boom")
    assert len(warnings) == 1


def test_notice_cleared_when_snapshots_arrive(window):
    window.restore_page.set_notice("No backups found yet — nothing to restore.")
    window._on_snapshots_ready(
        [
            {
                "id": "abcd1234",
                "short_id": "abcd1234",
                "time": "2026-01-01T00:00:00Z",
                "paths": ["/tmp"],
            }
        ]
    )
    assert not window.restore_page._notice_label.isVisibleTo(window.restore_page)
    assert window.restore_page._table.rowCount() == 1


def test_restore_page_notice_lifecycle(qapp):
    page = RestorePage()
    assert not page._notice_label.isVisibleTo(page)

    page.set_notice("hello")
    assert page._notice_label.isVisibleTo(page)
    assert page._notice_label.text() == "hello"

    page.set_snapshots([])
    assert not page._notice_label.isVisibleTo(page)

    page.set_notice("again")
    page.set_loading(True)
    assert not page._notice_label.isVisibleTo(page)

    page.set_notice("once more")
    page.clear_notice()
    assert not page._notice_label.isVisibleTo(page)
    assert page._notice_label.text() == ""
