"""Async wrapper around rclone for cloud storage backends.

Packrat talks to OneDrive/Google Drive by pointing restic at an
``rclone:<remote>:<path>`` location. This module lists remotes, creates
the packrat subfolder, and provides capacity estimates.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from .tools import rclone_path


class RcloneError(RuntimeError):
    pass


class RcloneRunner(QObject):
    """Async helpers around the rclone CLI."""

    finished = pyqtSignal(bool, str)  # success, message
    remotes_listed = pyqtSignal(list)  # remote names

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._pending: Optional[str] = None

    @staticmethod
    def available() -> bool:
        return rclone_path() is not None

    @staticmethod
    def binary() -> Optional[str]:
        return rclone_path()

    def is_running(self) -> bool:
        return (
            self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def _launch(self, args: List[str]) -> None:
        if self.is_running():
            raise RcloneError("An rclone operation is already running")
        binary = rclone_path()
        if not binary:
            raise RcloneError("rclone binary not found on this system")
        proc = QProcess(self)
        proc.setProgram(binary)
        proc.setArguments(args)
        proc.finished.connect(lambda code, status: self._on_finished(proc, code))
        self._process = proc
        self._buffer = ""
        proc.readyReadStandardOutput.connect(lambda: self._read(proc))
        proc.start()

    def _read(self, proc: QProcess) -> None:
        self._buffer += bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")

    def _on_finished(self, proc: QProcess, exit_code: int) -> None:
        self._process = None
        stdout = self._buffer
        self._buffer = ""
        stderr = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        proc.deleteLater()
        success = exit_code == 0
        if self._pending == "list_remotes":
            remotes = [line.strip().rstrip(":") for line in stdout.splitlines() if line.strip()]
            self.remotes_listed.emit(remotes)
            self._pending = None
            return
        message = stderr.strip() or stdout.strip() or ("Done" if success else "Failed")
        self._pending = None
        self.finished.emit(success, message)

    # ------------------------------------------------------------------ operations
    def list_remotes(self) -> None:
        self._pending = "list_remotes"
        self._launch(["listremotes"])

    def make_dir(self, remote: str, path: str) -> None:
        self._pending = "mkdir"
        self._launch(["mkdir", f"{remote}:{path}"])

    def lsd(self, remote: str, path: str = "") -> None:
        self._pending = "lsd"
        self._launch(["lsd", f"{remote}:{path}" if path else f"{remote}:"])

    def about(self, remote: str) -> None:
        self._pending = "about"
        self._launch(["about", f"{remote}:"])

    def purge(self, remote: str, path: str) -> None:
        """Delete a directory and everything under it."""
        self._pending = "purge"
        self._launch(["purge", f"{remote}:{path}"])


def list_remotes_sync() -> List[str]:
    """Synchronous remote listing, used by tests and CLI fallbacks."""
    import subprocess

    binary = rclone_path()
    if not binary:
        return []
    try:
        result = subprocess.run(
            [binary, "listremotes"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]
