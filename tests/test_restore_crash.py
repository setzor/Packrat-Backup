"""Regression tests: clicking Refresh must never crash the app.

Previously the Refresh button slot only caught ``BackendError`` while
``ResticRunner`` raises ``ResticProcessError`` (e.g. when a listing is
already running against a slow rclone remote). An unhandled exception in
a PyQt slot aborts the whole process (qFatal), which is what the user
observed on the Restore page with a OneDrive rclone remote.
"""

import pytest

pytest.importorskip("PyQt6")

from packrat.backend import BackupBackend
from packrat.main import MainWindow
from packrat.restic import ResticProcessError
from packrat.settings import Settings


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    win = MainWindow(settings)
    win.backend.set_password("test-password")
    yield win
    win.tray.hide()
    win.close()


def test_refresh_while_operation_running_does_not_raise(window, monkeypatch):
    def boom(*args, **kwargs):
        raise ResticProcessError("A restic operation is already running")

    monkeypatch.setattr(BackupBackend, "list_snapshots", boom)

    window.refresh_snapshots()
    window.restore_page._refresh_button.click()


def test_refresh_without_restic_binary_does_not_raise(window, monkeypatch):
    def boom(*args, **kwargs):
        raise ResticProcessError("restic binary not found on this system")

    monkeypatch.setattr(BackupBackend, "list_snapshots", boom)

    window.refresh_snapshots()
    window.restore_page._refresh_button.click()


def test_refresh_skipped_while_backend_busy(window, monkeypatch):
    called = []
    monkeypatch.setattr(
        BackupBackend, "list_snapshots", lambda self: called.append(True)
    )
    monkeypatch.setattr(
        BackupBackend, "is_busy", lambda self: True
    )

    window.refresh_snapshots()
    window.restore_page._refresh_button.click()

    assert called == []
