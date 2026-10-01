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
    monkeypatch.setattr(BackupBackend, "list_snapshots", lambda self: called.append(True))
    monkeypatch.setattr(BackupBackend, "is_busy", lambda self: True)

    window.refresh_snapshots()
    window.restore_page._refresh_button.click()

    assert called == []


def test_backend_signals_connected(qapp, tmp_path, monkeypatch):
    from packrat.backend import BackupBackend
    from packrat.settings import Settings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    backend = BackupBackend(Settings())
    receivers = backend.receivers(backend.snapshots_ready)
    assert backend.restic.receivers(backend.restic.snapshots_listed) >= 1
    assert backend.restic.receivers(backend.restic.files_listed) >= 1
    assert backend.rclone.receivers(backend.rclone.remotes_listed) >= 1
    assert receivers >= 0


def test_snapshot_cache_skips_rapid_reloads(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "refresh_snapshots", lambda: calls.append(True))
    # No snapshots loaded yet: first visit loads.
    window.show_snapshots()
    assert calls == [True]
    # Simulate a completed load.
    import datetime as dt

    window._snapshots_loaded_at = dt.datetime.now()
    window._snapshots_loaded_after_backup = window.settings.last_backup_time
    # Rapid revisit: cached, no reload.
    window.show_snapshots()
    assert calls == [True]
    # A finished backup invalidates the cache.
    window.settings.last_backup_time = "2026-09-30T12:00:00"
    window.show_snapshots()
    assert calls == [True, True]


def test_snapshot_cache_expires_after_interval(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "refresh_snapshots", lambda: calls.append(True))
    import datetime as dt

    window._snapshots_loaded_at = dt.datetime.now() - dt.timedelta(minutes=61)
    window._snapshots_loaded_after_backup = window.settings.last_backup_time
    window.show_snapshots()
    assert calls == [True]


def test_snapshot_cache_disabled_always_reloads(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "refresh_snapshots", lambda: calls.append(True))
    import datetime as dt

    window.settings.restore_refresh_minutes = 0
    window._snapshots_loaded_at = dt.datetime.now()
    window._snapshots_loaded_after_backup = window.settings.last_backup_time
    window.show_snapshots()
    assert calls == [True]


def test_cleanup_finish_clears_cleaning_state(window, monkeypatch):
    monkeypatch.setattr(window.tray, "show_message", lambda *a, **k: None)
    assert window.schedule_page._clean_now_button.text() == "Clean Up Now"
    window.schedule_page.set_cleaning(True)
    assert window.schedule_page._clean_now_button.text() == "Cleaning…"
    window.job.last_operation = "prune"
    window.job._on_operation_finished("prune", True, "Cleanup complete")
    assert window.schedule_page._clean_now_button.text() == "Clean Up Now"
    assert window.schedule_page._clean_now_button.isEnabled()
