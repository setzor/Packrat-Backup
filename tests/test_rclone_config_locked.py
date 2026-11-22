"""Password-protected rclone config must fail fast and say so clearly.

When the rclone config file is encrypted, rclone blocks on an interactive
"Enter configuration password:" prompt reading stdin. A QProcess child gets
a stdin pipe that stays open, so Packrat used to hang with no response at
all. Packrat now passes ``--ask-password=false`` and /dev/null stdin, and
translates the resulting error into an actionable message.
"""

import base64
import shutil
import subprocess

import pytest

pytest.importorskip("PyQt6")

from packrat.pages.storage import StoragePage
from packrat.rclone import (
    RcloneRunner,
    config_locked_message,
    is_config_locked,
    list_remotes_sync,
)
from packrat.rclone_setup import CONFIG_ERROR_ITEM
from packrat.restic import _result_message
from packrat.wizard import _DestinationPage

ASK_PASSWORD_FALSE_STDERR = (
    'CRITICAL: Failed to load config file "/tmp/rclone.conf": unable to decrypt '
    "configuration and not allowed to ask for password - set RCLONE_CONFIG_PASS "
    "to your configuration password\n"
)
PROMPT_STDERR = "Enter configuration password:\npassword:CRITICAL: Failed to read line: EOF\n"
WRONG_PASSWORD_STDERR = (
    "Enter configuration password:\n"
    "password:ERROR : Couldn't decrypt configuration, most likely wrong password.\n"
)


def _write_fake_encrypted_config(path):
    """Config header that makes rclone treat the file as password-protected."""
    ciphertext = base64.b64encode(b"x" * 64).decode()
    path.write_text(f"# Encrypted rclone configuration File\n\nRCLONE_ENCRYPT_V0:\n{ciphertext}\n")


# ------------------------------------------------------------- classification
def test_is_config_locked_matches_ask_password_false_error():
    assert is_config_locked(ASK_PASSWORD_FALSE_STDERR)


def test_is_config_locked_matches_prompt_eof_error():
    assert is_config_locked(PROMPT_STDERR)


def test_is_config_locked_matches_wrong_password_error():
    assert is_config_locked(WRONG_PASSWORD_STDERR)


def test_is_config_locked_ignores_other_errors():
    assert not is_config_locked("ERROR: couldn't open remote: connection refused")
    assert not is_config_locked("")


def test_config_locked_message_is_actionable():
    msg = config_locked_message()
    assert "password-protected" in msg
    assert "RCLONE_CONFIG_PASS" in msg
    assert "rclone config" in msg
    assert "unencrypt" in msg


def test_result_message_maps_config_locked_to_friendly_text():
    msg = _result_message("backup", False, 1, ASK_PASSWORD_FALSE_STDERR, repo="rclone:x:y")
    assert msg == config_locked_message()
    assert "CRITICAL" not in msg


# ------------------------------------------------------------- runner plumbing
class _FakeProc:
    def __init__(self, stderr=b""):
        self._stderr = stderr

    def readAllStandardError(self):
        return self._stderr

    def deleteLater(self):
        pass


def _capture_runner():
    runner = RcloneRunner()
    runner._buffer = ""
    events = {"finished": [], "remotes": []}
    runner.finished.connect(lambda ok, msg: events["finished"].append((ok, msg)))
    runner.remotes_listed.connect(lambda remotes: events["remotes"].append(remotes))
    return runner, events


def test_list_remotes_success_emits_remotes_only(qapp):
    runner, events = _capture_runner()
    runner._pending = "list_remotes"
    runner._buffer = "onedrive:\ngdrive:\n"
    runner._on_finished(_FakeProc(), 0)
    assert events["remotes"] == [["onedrive", "gdrive"]]
    assert events["finished"] == []


def test_list_remotes_config_locked_emits_finished_not_empty_list(qapp):
    runner, events = _capture_runner()
    runner._pending = "list_remotes"
    runner._buffer = ""
    runner._on_finished(_FakeProc(ASK_PASSWORD_FALSE_STDERR.encode()), 1)
    assert events["remotes"] == []
    assert events["finished"] == [(False, config_locked_message())]


def test_other_op_config_locked_gets_friendly_message(qapp):
    runner, events = _capture_runner()
    runner._pending = "mkdir"
    runner._on_finished(_FakeProc(PROMPT_STDERR.encode()), 1)
    assert events["finished"] == [(False, config_locked_message())]


def test_other_op_failure_keeps_raw_stderr(qapp):
    runner, events = _capture_runner()
    runner._pending = "mkdir"
    runner._on_finished(_FakeProc(b"ERROR: quota exceeded\n"), 1)
    assert events["finished"] == [(False, "ERROR: quota exceeded")]


class _FakeSignal:
    def connect(self, *args):
        pass


class _FakeQProcess:
    def __init__(self, parent=None):
        self.arguments = None
        self.stdin_file = None
        self.finished = _FakeSignal()
        self.readyReadStandardOutput = _FakeSignal()

    def setProgram(self, program):
        pass

    def setArguments(self, args):
        self.arguments = list(args)

    def setStandardInputFile(self, file_name):
        self.stdin_file = file_name

    def start(self):
        pass


def test_launch_never_waits_on_password_prompt(qapp, monkeypatch):
    import packrat.rclone as rclone_mod

    monkeypatch.setattr(rclone_mod, "rclone_path", lambda: "/usr/bin/rclone")
    monkeypatch.setattr(rclone_mod, "QProcess", _FakeQProcess)
    runner = RcloneRunner()
    runner.list_remotes()
    proc = runner._process
    assert proc.arguments[0] == "--ask-password=false"
    assert proc.arguments[1] == "listremotes"
    assert proc.stdin_file == "/dev/null"


# ------------------------------------------------------------- real rclone binary
@pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone not installed")
def test_real_rclone_fails_fast_and_classified_with_encrypted_config(tmp_path):
    rclone = shutil.which("rclone")
    conf = tmp_path / "rclone.conf"
    _write_fake_encrypted_config(conf)
    env = {"RCLONE_CONFIG": str(conf), "PATH": "/usr/local/bin:/usr/bin:/bin"}
    completed = subprocess.run(
        [rclone, "--ask-password=false", "listremotes"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    assert completed.returncode == 1
    assert is_config_locked(completed.stderr)


@pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone not installed")
def test_list_remotes_sync_does_not_hang_on_encrypted_config(tmp_path, monkeypatch):
    conf = tmp_path / "rclone.conf"
    _write_fake_encrypted_config(conf)
    monkeypatch.setenv("RCLONE_CONFIG", str(conf))
    monkeypatch.delenv("RCLONE_CONFIG_PASS", raising=False)
    assert list_remotes_sync() == []


# ------------------------------------------------------------- UI surfaces
def test_storage_page_shows_rclone_error_and_recovers(qapp):
    page = StoragePage(RcloneRunner())
    page._remote_radio.setChecked(True)
    page._refresh_button.setEnabled(False)
    page._on_rclone_finished(False, config_locked_message())
    assert page._help_label.text() == config_locked_message()
    assert page._refresh_button.isEnabled()
    assert page._remote_combo.itemText(0) == CONFIG_ERROR_ITEM
    saved = page.save()
    assert saved["rclone_remote"] == ""


def test_storage_page_success_leaves_help_alone(qapp):
    page = StoragePage(RcloneRunner())
    page._help_label.setText("previous")
    page._on_rclone_finished(True, "Done")
    assert page._help_label.text() == "previous"


def test_wizard_destination_page_shows_rclone_error(qapp):
    page = _DestinationPage(RcloneRunner())
    page._cloud_radio.setChecked(True)
    page._on_rclone_finished(False, config_locked_message())
    assert page._help_label.text() == config_locked_message()
    assert page._remote_combo.currentText() == CONFIG_ERROR_ITEM
    assert page.isComplete() is False
    assert page.config()["rclone_remote"] == ""
