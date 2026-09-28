import subprocess

from packrat.rclone import RcloneRunner, list_remotes_sync


def test_available():
    assert RcloneRunner.available() == (
        subprocess.run(["which", "rclone"], capture_output=True).returncode == 0
    )


def test_list_remotes_sync_no_crash():
    remotes = list_remotes_sync()
    assert isinstance(remotes, list)


def test_runner_not_running_initially(qapp):
    runner = RcloneRunner()
    assert runner.is_running() is False
