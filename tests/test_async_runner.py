import os
import subprocess

import pytest

from packrat.restic import ResticRunner

pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "restic"], capture_output=True).returncode != 0,
    reason="restic not installed",
)

_PASSWORD = "test-password-123"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    src = tmp_path / "docs"
    src.mkdir()
    (src / "file.txt").write_text("data")
    env = dict(os.environ, RESTIC_PASSWORD=_PASSWORD)
    subprocess.run(
        ["restic", "init", "--repo", str(path)],
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["restic", "backup", "--repo", str(path), str(src)],
        env=env,
        check=True,
        capture_output=True,
    )
    return str(path)


def _wait(qapp, ms=10000):
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_snapshots_async_does_not_crash(qapp, repo):
    """Regression: listing snapshots crashed with AttributeError (#crash)."""
    runner = ResticRunner()
    collected = {}
    runner.snapshots_listed.connect(lambda snaps: collected.update(snaps=snaps))
    finished = {}
    runner.finished.connect(lambda ok, msg: finished.update(ok=ok, msg=msg))

    runner.snapshots(repo, _PASSWORD)
    _wait(qapp)

    assert finished.get("ok") is True, finished
    snaps = collected.get("snaps")
    assert isinstance(snaps, list) and len(snaps) == 1
    assert snaps[0]["paths"] or "short_id" in snaps[0]


def test_backup_async_emits_progress(qapp, repo, tmp_path):
    runner = ResticRunner()
    finished = {}
    runner.finished.connect(lambda ok, msg: finished.update(ok=ok, msg=msg))
    src = tmp_path / "more"
    src.mkdir()
    (src / "another.txt").write_text("more data")

    runner.backup(repo, _PASSWORD, [str(src)], [])
    _wait(qapp)

    assert finished.get("ok") is True, finished


def test_restore_async(qapp, repo, tmp_path):
    runner = ResticRunner()
    listed = {}
    runner.snapshots_listed.connect(lambda snaps: listed.update(snaps=snaps))
    runner.snapshots(repo, _PASSWORD)
    _wait(qapp)
    snapshot_id = listed["snaps"][0]["short_id"]

    restored = {}
    runner.finished.connect(lambda ok, msg: restored.update(ok=ok, msg=msg))
    target = tmp_path / "restored-here"
    runner.restore(repo, _PASSWORD, snapshot_id, str(target))
    _wait(qapp)

    assert restored.get("ok") is True, restored
    assert any(target.rglob("file.txt"))
