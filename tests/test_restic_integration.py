import json
import os
import subprocess

import pytest

from packrat.restic import (
    ResticRunner,
    _parse_snapshots,
    _result_message,
    keep_args_from_settings,
)
from packrat.settings import Settings

pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "restic"], capture_output=True).returncode != 0,
    reason="restic not installed",
)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    env = dict(os.environ, RESTIC_PASSWORD="test-password-123")
    subprocess.run(
        ["restic", "init", "--repo", str(path)],
        env=env,
        check=True,
        capture_output=True,
    )
    return str(path)


def _env():
    return dict(os.environ, RESTIC_PASSWORD="test-password-123")


def test_init_backup_snapshots_restore_roundtrip(repo, tmp_path):
    src = tmp_path / "docs"
    src.mkdir()
    (src / "hello.txt").write_text("hello packrat")

    env = _env()
    subprocess.run(
        ["restic", "backup", "--repo", repo, str(src)],
        env=env,
        check=True,
        capture_output=True,
    )
    listing = subprocess.run(
        ["restic", "snapshots", "--json", "--repo", repo],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    snapshots = json.loads(listing.stdout)
    assert len(snapshots) == 1

    target = tmp_path / "restored"
    subprocess.run(
        ["restic", "restore", snapshots[0]["short_id"], "--repo", repo, "--target", str(target)],
        env=env,
        check=True,
        capture_output=True,
    )
    restored = next(p for p in target.rglob("hello.txt") if p.is_file())
    assert restored.read_text() == "hello packrat"


def test_parse_snapshots_json():
    payload = [{"short_id": "abc12345", "time": "2026-09-28T12:00:00"}]
    assert _parse_snapshots(json.dumps(payload)) == payload
    wrapped = {"message_type": "snapshots_list", "snapshots": payload}
    assert _parse_snapshots(json.dumps(wrapped)) == payload
    assert _parse_snapshots("") == []


def test_result_message_contains_stderr_hint():
    msg = _result_message("backup", False, 1, "Fatal: wrong password or no key")
    assert "wrong password" in msg


def test_keep_args_from_settings():
    s = Settings()
    s.keep_hourly = 0
    s.keep_daily = 7
    s.keep_weekly = 5
    s.keep_monthly = 12
    s.keep_yearly = 3
    s.keep_within = "1m"
    args = keep_args_from_settings(s)
    assert args == [
        "--keep-daily",
        "7",
        "--keep-weekly",
        "5",
        "--keep-monthly",
        "12",
        "--keep-yearly",
        "3",
        "--keep-within",
        "1m",
    ]


def test_runner_reports_missing_binary():
    runner = ResticRunner()
    assert runner.is_running() is False


def test_prune_removes_old_snapshots(repo, tmp_path):
    src = tmp_path / "docs"
    src.mkdir()
    (src / "v1.txt").write_text("one")
    env = _env()
    subprocess.run(
        ["restic", "backup", "--repo", repo, str(src), "--tag", "old"],
        env=env,
        check=True,
        capture_output=True,
    )
    import time

    time.sleep(1.1)
    (src / "v2.txt").write_text("two")
    subprocess.run(
        ["restic", "backup", "--repo", repo, str(src)],
        env=env,
        check=True,
        capture_output=True,
    )
    before = subprocess.run(
        ["restic", "snapshots", "--json", "--repo", repo],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(json.loads(before.stdout)) == 2
    subprocess.run(
        [
            "restic",
            "forget",
            "--prune",
            "--keep-last",
            "1",
            "--repo",
            repo,
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    after = subprocess.run(
        ["restic", "snapshots", "--json", "--repo", repo],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(json.loads(after.stdout)) == 1
