import stat
import textwrap

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
            "total_bytes": 200 * 1024**3,
            "bytes_remaining": 190 * 1024**3,
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


def test_speed_and_eta_appear_after_samples():
    from packrat.restic import ResticRunner

    runner = ResticRunner()
    seen = []
    runner.progress.connect(lambda pct, msg: seen.append((pct, msg)))

    runner._speed_time = None
    runner._handle_backup_message(
        {"message_type": "status", "total_bytes": 1000, "bytes_remaining": 900}
    )
    runner._speed_time -= 2
    runner._handle_backup_message(
        {"message_type": "status", "total_bytes": 1000, "bytes_remaining": 800}
    )

    _, text = seen[-1]
    assert "/s" in text
    assert "left" in text


def test_eta_text_formatting():
    from packrat.restic import _eta_text

    assert _eta_text(45) == "45s"
    assert _eta_text(125) == "2m 5s"
    assert _eta_text(3700) == "1h 1m"
