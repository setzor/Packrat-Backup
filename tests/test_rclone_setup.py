from unittest import mock

from packrat import rclone_setup


def test_open_config_no_terminal(qapp):
    with mock.patch.object(rclone_setup, "_find_terminal", return_value=None):
        ok, msg = rclone_setup.open_rclone_config_ui()
    assert ok is False
    assert "rclone config" in msg


def test_open_config_launches_terminal(qapp):
    with (
        mock.patch.object(
            rclone_setup, "_find_terminal", return_value=("/usr/bin/konsole", ["-e"])
        ),
        mock.patch.object(rclone_setup, "rclone_path", return_value="/usr/local/bin/rclone"),
        mock.patch.object(rclone_setup.subprocess, "Popen") as popen,
    ):
        ok, msg = rclone_setup.open_rclone_config_ui()
    assert ok is True
    assert "'n' for a new remote" in msg
    assert "onedrive" in msg
    popen.assert_called_once_with(["/usr/bin/konsole", "-e", "/usr/local/bin/rclone", "config"])


def test_open_config_without_rclone(qapp):
    with (
        mock.patch.object(rclone_setup, "_find_terminal", return_value=None),
        mock.patch.object(rclone_setup, "rclone_path", return_value=None),
    ):
        ok, msg = rclone_setup.open_rclone_config_ui()
    assert ok is False
    assert "not installed" in msg


def test_help_texts_mention_refresh():
    assert "Refresh" in rclone_setup.no_remotes_help()
    assert "dnf" in rclone_setup.rclone_missing_help()
