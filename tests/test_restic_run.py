import stat
import textwrap

import pytest

from packrat.restic import Restic


def _fake_restable(tmp_path, body):
    path = tmp_path / "fake-restic"
    path.write_text(textwrap.dedent(body).lstrip())
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_restic_run_preserves_flags_and_sets_password_env(tmp_path, monkeypatch):
    binary = _fake_restable(
        tmp_path,
        """
        #!/bin/sh
        echo "ARGS: $@"
        echo "RESTIC_PASSWORD: $RESTIC_PASSWORD"
        """,
    )
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", binary)
    ok, stdout, _ = Restic.run(
        ["--repo", "rclone:myremote:packrat-backups", "cat", "config"],
        timeout=10,
        password="s3cret",
    )
    assert ok is True
    assert "ARGS: --repo rclone:myremote:packrat-backups cat config" in stdout
    assert "RESTIC_PASSWORD: s3cret" in stdout


def test_restic_run_without_password_clears_inherited_env(tmp_path, monkeypatch):
    binary = _fake_restable(
        tmp_path,
        """
        #!/bin/sh
        echo "RESTIC_PASSWORD: ${RESTIC_PASSWORD:-unset}"
        """,
    )
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", binary)
    monkeypatch.setenv("RESTIC_PASSWORD", "leaked-from-parent")
    ok, stdout, _ = Restic.run(["cat", "config"], timeout=10)
    assert ok is True
    assert "RESTIC_PASSWORD: unset" in stdout


def test_stderr_after_status_keeps_determinate_percent():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._last_percent = None
    runner._handle_backup_message({"message_type": "status", "percent_done": 0.03})
    runner._handle_backup_message({"message_type": "status", "percent_done": 0.01})
    runner._on_stderr_text("scanning /home")

    pcts = [p for p, _ in seen]
    assert pcts == [3, 3, 3]


def test_stderr_before_status_is_indeterminate():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._last_percent = None
    runner._on_stderr_text("unable to get xattr")

    assert seen == [(-1, "unable to get xattr")]


def test_percent_never_goes_backwards():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._last_percent = None
    for pct in (0.5, 0.2, 0.8, 0.7, 1.0):
        runner._handle_backup_message({"message_type": "status", "percent_done": pct})

    pcts = [p for p, _ in seen]
    assert pcts == sorted(pcts)
    assert pcts == [50, 50, 80, 80, 100]


def test_byte_counter_in_progress_text():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._handle_backup_message(
        {
            "message_type": "status",
            "percent_done": 0.94,
            "current_activity": "saving",
            "bytes_done": 10 * 1024**3,
            "total_bytes": 200 * 1024**3,
        }
    )

    pct, text = seen[-1]
    assert pct == 94
    assert "10.0 GiB of 200.0 GiB" in text
    assert "saving" in text


def test_byte_counter_absent_without_totals():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._handle_backup_message({"message_type": "status", "percent_done": 0.5})

    _, text = seen[-1]
    assert "of" not in text


def test_speed_and_eta_appear_after_samples_local():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    runner._repo_is_cloud = False
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._speed_time = None
    runner._handle_backup_message(
        {"message_type": "status", "bytes_done": 100, "total_bytes": 1000}
    )
    runner._speed_time -= 2
    runner._handle_backup_message(
        {"message_type": "status", "bytes_done": 200, "total_bytes": 1000}
    )

    _, text = seen[-1]
    assert "/s" in text
    assert "left" in text


def test_cloud_repo_shows_no_bogus_speed_or_eta():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    runner._repo_is_cloud = True
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    GiB = 1024**3
    runner._handle_backup_message(
        {"message_type": "status", "bytes_done": 190 * GiB, "total_bytes": 200 * GiB}
    )
    runner._handle_backup_message(
        {"message_type": "status", "bytes_done": 195 * GiB, "total_bytes": 200 * GiB}
    )

    _, text = seen[-1]
    assert "processed" in text
    assert "/s" not in text
    assert "left" not in text


def test_cloud_tick_shows_uploading_note():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    runner._repo_is_cloud = True
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._process = _RunningProc()
    runner._operation = "backup"
    runner._last_percent = 77
    runner._last_total_bytes = 200 * 1024**3
    runner._last_bytes_done = 150 * 1024**3
    runner._tick_stale_speed()

    pct, text = seen[-1]
    assert pct == 77
    assert "uploading to the cloud" in text
    assert "/s" not in text


def test_eta_text_formatting():
    from packrat.restic import _eta_text

    assert _eta_text(45) == "45s"
    assert _eta_text(125) == "2m 5s"
    assert _eta_text(3700) == "1h 1m"


def test_byte_counter_done_equals_total_shows_finishing():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._handle_backup_message(
        {
            "message_type": "status",
            "percent_done": 0.77,
            "current_activity": "saving",
            "bytes_done": 120.6 * 1024**3,
            "total_bytes": 120.6 * 1024**3,
        }
    )

    pct, text = seen[-1]
    assert pct == 77
    assert "all data processed" in text
    assert "0s" not in text
    assert "of" not in text


def test_clean_ansi_strips_escape_sequences():
    from packrat.restic import _clean_ansi

    noisy = "\x1b[31mFatal:\x1b[0m repository does not exist\x1b[?25h"
    assert _clean_ansi(noisy) == "Fatal: repository does not exist"


def test_result_message_includes_accumulated_stderr_detail():
    from packrat.restic import _result_message

    stderr = "\x1b[31mFatal:\x1b[0m unable to open config file\n"
    msg = _result_message("prune", False, 11, stderr)
    assert "Cleanup complete failed (exit 11)" in msg
    assert "unable to open config file" in msg
    assert "\x1b" not in msg


def test_result_message_detail_survives_empty_drained_pipe():
    from packrat.restic import _result_message

    assert _result_message("prune", False, 11, "") == "Cleanup complete failed (exit 11)"


def test_stderr_progress_lines_are_ansi_cleaned():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._last_percent = None
    runner._on_stderr_text("\x1b[36mTransferred: 3 GiB / 3 GiB, 100%\x1b[0m\r")

    pct, text = seen[-1]
    assert pct == -1
    assert "\x1b" not in text
    assert "Transferred" in text


def test_result_message_detects_stale_lock():
    from packrat.restic import _result_message

    stderr = "repository is already locked, lock file ... created at ...\nthe `unlock` command can be used to remove stale locks\n"
    msg = _result_message("prune", False, 11, stderr)
    assert "exit 11" in msg
    assert "unlock" in msg


def test_delete_interrupted_tmp_files_local(tmp_path):
    """Abandoned -tmp- pack files are removed; real packs survive."""
    import glob

    QtCore = pytest.importorskip("PyQt6.QtCore")
    pytest.skip("requires full PyQt6 widgets") if not hasattr(QtCore, "QSettings") else None
    from packrat.backend import BackupBackend
    from packrat.settings import Backend, Settings

    repo = tmp_path / "repo"
    data = repo / "data" / "ab"
    data.mkdir(parents=True)
    (data / "ab12...-tmp-123").write_bytes(b"partial upload")
    (data / "ab12...definitely-a-pack").write_bytes(b"real pack")

    s = Settings()
    s.backend_cfg.backend = Backend.LOCAL
    s.backend_cfg.local_path = str(repo)
    b = BackupBackend(s)

    ok, detail = b.delete_interrupted_tmp_files()

    assert ok
    assert not glob.glob(str(repo / "data" / "*" / "*-tmp-*"))
    assert (data / "ab12...definitely-a-pack").exists()


def test_has_snapshots_unknown_defaults_true():
    QtCore = pytest.importorskip("PyQt6.QtCore")
    if not hasattr(QtCore, "QSettings"):
        pytest.skip("requires full PyQt6 widgets")
    from packrat.backend import BackupBackend

    class _Settings:
        backend_cfg = None

    b = BackupBackend.__new__(BackupBackend)
    b._snapshot_count = None
    assert b.has_snapshots() is True
    b._snapshot_count = 0
    assert b.has_snapshots() is False
    b._snapshot_count = 3
    assert b.has_snapshots() is True


class _RunningProc:
    def state(self):
        return 1


def test_speed_decays_when_bytes_stop_advancing():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    runner._repo_is_cloud = False
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._speed_time = None
    GiB = 1024**3
    runner._handle_backup_message(
        {
            "message_type": "status",
            "percent_done": 0.9,
            "bytes_done": 180 * GiB,
            "total_bytes": 200 * GiB,
        }
    )
    runner._speed_time -= 5
    runner._handle_backup_message(
        {
            "message_type": "status",
            "percent_done": 0.9,
            "bytes_done": 190 * GiB,
            "total_bytes": 200 * GiB,
        }
    )
    fast = runner._speed_bytes_per_sec
    assert fast > 0
    runner._speed_time -= 60
    runner._last_bytes_done = 190 * GiB

    runner._process = _RunningProc()
    runner._operation = "backup"
    runner._last_percent = 90
    runner._last_total_bytes = 200 * GiB
    runner._last_bytes_done = 190 * GiB
    runner._tick_stale_speed()
    decayed = runner._speed_bytes_per_sec
    assert decayed < fast
    pct, text = seen[-1]
    assert pct == 90
    assert "190.0 GiB of 200.0 GiB" in text
    if decayed < 1:
        assert "waiting for the cloud upload" in text


def test_backup_exit3_with_snapshot_is_partial_success():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.finished.connect(lambda ok, msg: seen.append((ok, msg)))

    runner._operation = "backup"
    runner._stopping = False
    runner.last_snapshot_id = "abc123"
    runner.last_backup_summary = {"total_files_processed": 1234, "data_added": 5 * 1024**3}
    stderr = (
        '{"message_type":"error","error":{"message":"/home/x/y: permission denied"},'
        '"during":"archival","item":"/home/x/y"}\n'
        '{"message_type":"exit_error","code":3,'
        '"message":"Warning: at least one source file could not be read"}\n'
    )
    runner._stderr_text = stderr
    runner._process = None
    runner._on_finished(3, 0)

    ok, msg = seen[-1]
    assert ok is True
    assert "snapshot of 1234 files" in msg
    assert "could not be read" in msg


def test_unreadable_files_collected_from_error_messages():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    runner._handle_backup_message(
        {
            "message_type": "error",
            "item": "/home/user/.config/google-chrome/SingletonLock",
            "error": {"message": "open: permission denied"},
        }
    )
    runner._handle_backup_message(
        {
            "message_type": "error",
            "item": "/home/user/.cache/big/dir/with/very/long/path/somefile.db",
            "error": {"message": "no such file or directory"},
        }
    )
    runner._handle_backup_message(
        {
            "message_type": "error",
            "item": "/home/user/.config/google-chrome/SingletonLock",
            "error": {"message": "open: permission denied"},
        }
    )

    assert runner.unreadable_files == [
        "/home/user/.config/google-chrome/SingletonLock: open: permission denied",
        "/home/user/.cache/big/dir/with/very/long/path/somefile.db: no such file or directory",
    ]


def test_adopt_newest_snapshot_time_reconciles_overdue_badge():
    QtCore = pytest.importorskip("PyQt6.QtCore")
    if not hasattr(QtCore, "QSettings"):
        pytest.skip("requires full PyQt6 widgets")

    from packrat.main import MainWindow

    win = MainWindow.__new__(MainWindow)

    class _Settings:
        last_backup_time = "2026-10-01T08:00:00"
        save_calls = 0

        def save(self):
            self.save_calls += 1

    class _Overview:
        refreshed = 0

        def set_state(self, *a, **k):
            pass

    win.settings = _Settings()
    win.overview_page = _Overview()
    win._refresh_overview = lambda: None

    snapshots = [{"time": "2026-10-09T04:06:42.533518173Z"}]
    win._adopt_newest_snapshot_time(snapshots)
    assert win.settings.last_backup_time.startswith("2026-10-09")
    assert win.settings.save_calls == 1

    older = [{"time": "2026-09-01T00:00:00Z"}]
    before = win.settings.last_backup_time
    win._adopt_newest_snapshot_time(older)
    assert win.settings.last_backup_time == before


def test_dry_run_exit3_with_summary_is_partial_success():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    finished = []
    runner.finished.connect(lambda ok, msg: finished.append((ok, msg)))
    dry_runs = []
    runner.dry_run_ready.connect(lambda s: dry_runs.append(s))

    runner._operation = "dry-run"
    runner._stopping = False
    runner._process = None
    runner._buffer = (
        '{"message_type":"status","percent_done":0.5,"total_bytes":100,"bytes_done":50}\n'
        '{"message_type":"summary","files_new":12,"files_changed":0,'
        '"total_files_processed":120,"total_bytes_processed":5000,'
        '"data_added":3000,"snapshot_id":"x","dry_run":true}\n'
    )
    runner._stderr_text = (
        '{"message_type":"error","error":{"message":"/tmp/f: permission denied"},'
        '"during":"archival","item":"/tmp/f"}\n'
        '{"message_type":"exit_error","code":3,'
        '"message":"Warning: at least one source file could not be read"}\n'
    )
    runner._on_finished(3, 0)

    ok, msg = finished[-1]
    assert ok is True
    assert "Preview ready" in msg
    assert "could not be read" in msg
    assert dry_runs and dry_runs[0]["total_files_processed"] == 120


def test_activity_log_trimmed_to_max_entries(tmp_path, monkeypatch):
    from packrat import activity

    monkeypatch.setattr(activity, "log_path", lambda: tmp_path / "activity.jsonl")
    for i in range(activity.MAX_ENTRIES + 50):
        activity.log_run("backup", True, f"run {i}", "2026-10-09T00:00:00")

    lines = [ln for ln in (tmp_path / "activity.jsonl").read_text().splitlines() if ln.strip()]
    assert len(lines) == activity.MAX_ENTRIES
    import json

    first = json.loads(lines[0])
    assert first["message"] == "run 50"
