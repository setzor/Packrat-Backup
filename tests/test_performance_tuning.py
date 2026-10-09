import textwrap

import pytest

from packrat.backend import BackupBackend
from packrat.restic import Restic, ResticRunner, _extended_options
from packrat.settings import Backend, Settings


def _rclone_settings():
    settings = Settings()
    settings.backend_cfg.backend = Backend.RCLONE
    settings.backend_cfg.rclone_remote = "myremote"
    settings.backend_cfg.rclone_path = "packrat-backups"
    settings.folders = ["/tmp/packrat-test-home/source"]
    return settings


def _local_settings():
    settings = Settings()
    settings.backend_cfg.backend = Backend.LOCAL
    settings.folders = ["/tmp/packrat-test-home/source"]
    return settings


def test_extended_options_empty_for_local_repo():
    assert _extended_options("/tmp/backups", {"connections": 8, "transfers": 8}) == []


def test_extended_options_pass_rclone_tuning():
    opts = {"connections": 8, "transfers": 8, "pack_size": 64}
    args = _extended_options("rclone:myremote:packrat-backups", opts)
    assert "rclone.timeout=5m" in args
    assert "rclone.connections=8" in args
    rclone_args = next(a for a in args if a.startswith("rclone.args="))
    assert rclone_args.startswith("rclone.args=serve restic --stdio")
    assert "--transfers=8" in rclone_args
    assert "--checkers=16" in rclone_args
    assert "--fast-list" in rclone_args
    assert "--buffer-size=32M" in rclone_args


def test_rclone_serve_args_accepted_by_rclone(tmp_path):
    """Every flag we inject must be valid for `rclone serve restic` (#64).

    restic spawns rclone with rclone.args; an unknown flag makes rclone
    exit immediately and every repository operation fail (regression:
    --dir-cache-time is a VFS flag, not a serve flag).
    """
    import shutil
    import subprocess

    rclone = shutil.which("rclone")
    if rclone is None:
        pytest.skip("rclone not installed")
    conf = tmp_path / "rclone.conf"
    conf.write_text("[test]\ntype = local\n")
    opts = {"connections": 8, "transfers": 8, "pack_size": 64}
    rclone_args = next(
        a for a in _extended_options("rclone:test:repo", opts) if a.startswith("rclone.args=")
    )
    assert rclone_args.startswith("rclone.args=")
    serve = rclone_args.split("=", 1)[1].split()
    completed = subprocess.run(
        [rclone, "--config", str(conf)] + serve + ["test:/does-not-exist"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
    )
    stderr = completed.stderr.decode("utf-8", errors="replace")
    assert completed.returncode == 0, stderr
    for flag in ("--stdio", "--checkers=16", "--fast-list", "--transfers=8", "--buffer-size=32M"):
        assert flag in serve


def test_backend_cloud_options_only_for_rclone(qapp):
    settings = _rclone_settings()
    settings.cloud_connections = 12
    settings.cloud_pack_size = 128
    backend = BackupBackend(settings)
    assert backend.cloud_options() == {"connections": 12, "transfers": 12, "pack_size": 128}

    local = BackupBackend(_local_settings())
    assert local.cloud_options() == {}


def test_backup_launch_passes_cloud_options(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="", options=None: (True, "{}", ""),
    )
    launched = {}

    def fake_backup(self, repo, password, folders, excludes, dry_run=False, options=None):
        launched["repo"] = repo
        launched["options"] = options

    monkeypatch.setattr(ResticRunner, "backup", fake_backup)
    backend.run_backup()
    assert launched["repo"] == "rclone:myremote:packrat-backups"
    assert launched["options"] == {
        "connections": 8,
        "transfers": 8,
        "pack_size": 64,
    }


def test_restic_run_injects_options_for_rclone_repo(tmp_path, monkeypatch):
    import stat

    path = tmp_path / "fake-restic"
    path.write_text(
        textwrap.dedent(
            """
            #!/bin/sh
            echo "ARGS: $@"
            echo "PACK_SIZE: ${RESTIC_PACK_SIZE:-unset}"
            """
        ).lstrip()
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", str(path))
    ok, stdout, _ = Restic.run(
        ["--repo", "rclone:myremote:packrat-backups", "backup", "/data"],
        timeout=10,
        options={"connections": 8, "transfers": 8, "pack_size": 64},
    )
    assert ok is True
    assert (
        "--repo rclone:myremote:packrat-backups -o rclone.timeout=5m -o rclone.connections=8"
        in stdout
    )
    assert "PACK_SIZE: 64" in stdout


def test_restic_run_local_repo_gets_no_rclone_options(tmp_path, monkeypatch):
    import stat

    path = tmp_path / "fake-restic"
    path.write_text('#!/bin/sh\necho "ARGS: $@"\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", str(path))
    ok, stdout, _ = Restic.run(
        ["--repo", "/tmp/backups", "backup", "/data"],
        timeout=10,
        options={"connections": 8, "transfers": 8, "pack_size": 64},
    )
    assert ok is True
    assert "ARGS: --repo /tmp/backups backup /data" in stdout


def test_repo_probe_cached_per_location(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    calls = []

    def fake_run(args, timeout=300, password="", options=None):
        calls.append(list(args))
        return True, "{}", ""

    monkeypatch.setattr("packrat.backend.Restic.run", fake_run)
    assert backend._repo_exists() is True
    assert backend._repo_exists() is True
    assert backend._repo_exists() is True
    assert len(calls) == 1


def test_prune_due_respects_interval(qapp):
    import datetime as dt

    backend = BackupBackend(_rclone_settings())
    backend.settings.auto_prune_interval_days = 7
    assert backend.prune_due() is True
    backend.settings.last_prune_time = dt.datetime.now().isoformat(timespec="seconds")
    assert backend.prune_due() is False
    backend.settings.last_prune_time = (dt.datetime.now() - dt.timedelta(days=8)).isoformat(
        timespec="seconds"
    )
    assert backend.prune_due() is True


def test_forget_applied_between_prunes(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    monkeypatch.setattr(
        "packrat.backend.Restic.run",
        lambda args, timeout=300, password="", options=None: (True, "{}", ""),
    )
    launched = []

    def fake_forget(self, repo, password, keep_args, options=None):
        launched.append(("forget", repo, list(keep_args)))

    monkeypatch.setattr(ResticRunner, "forget", fake_forget)
    backend.forget()
    op, repo, keep_args = launched[0]
    assert op == "forget"
    assert repo == "rclone:myremote:packrat-backups"
    assert "--keep-within" in keep_args


def test_settings_cloud_tuning_persisted(qapp):
    s = Settings()
    assert s.cloud_connections == 8
    assert s.cloud_pack_size == 64
    assert s.auto_prune_interval_days == 7
    s.cloud_connections = 16
    s.cloud_pack_size = 128
    s.auto_prune_interval_days = 30
    s.last_prune_time = "2026-10-03T12:00:00"
    s.save()
    s2 = Settings()
    assert s2.cloud_connections == 16
    assert s2.cloud_pack_size == 128
    assert s2.auto_prune_interval_days == 30
    assert s2.last_prune_time == "2026-10-03T12:00:00"


def test_settings_migrates_legacy_prune_every_run(qapp):
    s = Settings()
    s._settings.setValue("auto_prune_interval_days", 0)
    s._load()
    assert s.auto_prune_interval_days == 1


def test_settings_clamps_cloud_values(qapp):
    s = Settings()
    s._settings.setValue("cloud_connections", 99)
    s._settings.setValue("cloud_pack_size", 1)
    s._load()
    assert s.cloud_connections == 16
    assert s.cloud_pack_size == 16


def test_init_uses_repository_version_2(qapp, monkeypatch):
    launched = {}

    def fake_launch(repo, password, args, operation, working_dir=None, options=None):
        launched["args"] = list(args)

    runner = ResticRunner()
    monkeypatch.setattr(runner, "_launch", fake_launch)
    runner.init("rclone:myremote:packrat-backups", "pw")
    assert launched["args"] == ["init", "--repository-version", "2"]


def test_prune_and_forget_arg_shapes(qapp, monkeypatch):
    launched = []

    def fake_launch(repo, password, args, operation, working_dir=None, options=None):
        launched.append((operation, list(args)))

    runner = ResticRunner()
    monkeypatch.setattr(runner, "_launch", fake_launch)
    runner.forget("rclone:myremote:packrat-backups", "pw", ["--keep-daily", "7"])
    runner.prune("rclone:myremote:packrat-backups", "pw", ["--keep-daily", "7"])
    assert launched == [
        ("forget", ["forget", "--keep-daily", "7"]),
        ("prune", ["forget", "--prune", "--keep-daily", "7"]),
    ]


def test_init_clears_repo_probe_cache(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    calls = []

    def fake_run(args, timeout=300, password="", options=None):
        calls.append(list(args))
        return False, "", "Fatal: repository does not exist"

    monkeypatch.setattr("packrat.backend.Restic.run", fake_run)
    assert backend._repo_exists() is False
    assert backend._repo_exists() is False
    assert len(calls) == 1
    backend._on_restic_finished(True, "created")
    backend.restic._operation = "init"
    backend._on_restic_finished(True, "created")
    assert backend._repo_exists() is False
    assert len(calls) == 2


def test_transient_probe_error_not_cached(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    calls = []

    def fake_run(args, timeout=300, password="", options=None):
        calls.append(1)
        return False, "", "connection reset by peer"

    monkeypatch.setattr("packrat.backend.Restic.run", fake_run)
    assert backend._repo_exists() is False
    assert backend._repo_exists() is False
    assert len(calls) == 2


def test_check_and_verify_get_cloud_options(qapp, monkeypatch):
    backend = BackupBackend(_rclone_settings())
    launched = []

    def fake_check(self, repo, password, read_data="off", options=None):
        launched.append(("check", repo, read_data, options))

    monkeypatch.setattr(ResticRunner, "check", fake_check)
    monkeypatch.setattr(
        ResticRunner,
        "verify",
        lambda self, repo, password, read_data="sample", options=None: launched.append(
            ("verify", repo, read_data, options)
        ),
    )
    backend.check()
    backend.verify_backup()
    assert launched[0][0] == "check"
    assert launched[0][3] == {"connections": 8, "transfers": 8, "pack_size": 64}
    assert launched[1][0] == "verify"
    assert launched[1][3] == {"connections": 8, "transfers": 8, "pack_size": 64}


def test_forget_logged_in_activity(qapp):
    from packrat.jobs import BackupJob

    backend = BackupBackend(_rclone_settings())
    job = BackupJob(backend.settings, backend)
    job.last_operation = "forget"
    job._on_operation_finished("forget", True, "retention applied")
    import json

    from packrat.activity import log_path

    entries = [json.loads(line) for line in log_path().read_text().splitlines()]
    assert entries[-1]["operation"] == "forget"
    assert entries[-1]["success"] is True
