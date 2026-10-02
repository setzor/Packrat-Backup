"""Unified backup backend: local folders or rclone remotes.

Translates the user's settings into a restic repository location and
exposes high-level operations used by the UI and the scheduler.
"""

from __future__ import annotations

import os
from subprocess import SubprocessError
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .rclone import RcloneRunner
from .restic import Restic, ResticRunner, keep_args_from_settings
from .settings import Backend, Settings


class BackendError(RuntimeError):
    pass


class BackupBackend(QObject):
    """Facade over restic + (optionally) rclone."""

    operation_finished = pyqtSignal(str, bool, str)  # operation, success, message
    progress = pyqtSignal(int, str)
    snapshots_ready = pyqtSignal(list)
    remotes_ready = pyqtSignal(list)
    files_ready = pyqtSignal(list)
    check_finished = pyqtSignal(bool, str)

    def __init__(self, settings: Settings, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.restic = ResticRunner(self)
        self.rclone = RcloneRunner(self)
        self._password = ""
        self._initing_for_backup = False
        self.restic.finished.connect(self._on_restic_finished)
        self.restic.progress.connect(self.progress)
        self.restic.snapshots_listed.connect(self._on_snapshots)
        self.restic.files_listed.connect(self._on_files)
        self.rclone.remotes_listed.connect(self._on_remotes)

    def _backup_excludes(self) -> list:
        excludes = list(self.settings.exclude_patterns)
        excludes.extend(os.path.expanduser(f) for f in self.settings.ignored_folders)
        return excludes

    # ------------------------------------------------------------------ helpers
    def set_password(self, password: str) -> None:
        self._password = password

    def has_password(self) -> bool:
        return bool(self._password)

    def repo_location(self) -> str:
        cfg = self.settings.backend_cfg
        if cfg.backend is Backend.LOCAL:
            return os.path.expanduser(cfg.local_path)
        remote = cfg.rclone_remote
        if not remote:
            raise BackendError("No rclone remote configured")
        sub = cfg.rclone_path.strip("/")
        if not sub:
            raise BackendError("No rclone repository folder configured for this remote")
        return f"rclone:{remote}:{sub}"

    def is_configured(self) -> bool:
        try:
            return bool(self.repo_location())
        except BackendError:
            return False

    def prepare(self) -> None:
        """Ensure the destination directory/repository exists."""
        cfg = self.settings.backend_cfg
        if cfg.backend is Backend.LOCAL:
            path = os.path.expanduser(cfg.local_path)
            os.makedirs(path, exist_ok=True)

    def init_repository(self) -> None:
        self.prepare()
        self.restic.init(self.repo_location(), self._password)

    def run_backup(self) -> None:
        if not self.settings.folders:
            raise BackendError("No folders selected to back up")
        self.prepare()
        if not self._repo_exists():
            self.restic.init(self.repo_location(), self._password)
            self._initing_for_backup = True
            return
        self.restic.backup(
            self.repo_location(),
            self._password,
            self.settings.folders,
            self._backup_excludes(),
        )

    def _repo_exists(self) -> bool:
        """True when the configured restic repository exists.

        ``restic cat config`` is authoritative for every backend (local and
        rclone alike): exit code 10 means "repository does not exist" on
        restic >= 0.17. On older restic the exit code is a generic 1, so the
        stderr is scanned for the same wording restic uses there. Any
        password failure means the repository exists but cannot be opened.
        """
        try:
            repo = self.repo_location()
        except BackendError:
            return False
        try:
            ok, _, stderr = Restic.run(
                ["--repo", repo, "cat", "config"],
                timeout=60,
                password=self._password,
            )
        except (OSError, SubprocessError):
            ok, stderr = False, ""
        if ok:
            return True
        lowered = stderr.lower()
        if "repository does not exist" in lowered:
            return False
        if "no such file or directory" in lowered:
            return False
        if "is there a repository at the following location" in lowered:
            return False
        if "wrong password" in lowered or "password" in lowered:
            return True
        if self.settings.backend_cfg.backend is Backend.LOCAL:
            path = os.path.expanduser(self.settings.backend_cfg.local_path)
            return os.path.isdir(os.path.join(path, "keys"))
        return False

    def list_snapshots(self) -> None:
        self.restic.snapshots(self.repo_location(), self._password)

    def list_snapshot_files(self, snapshot_id: str) -> None:
        self.restic.list_files(self.repo_location(), self._password, snapshot_id)

    def restore_snapshot(self, snapshot_id: str, target: str) -> None:
        os.makedirs(os.path.expanduser(target), exist_ok=True)
        self.restic.restore(self.repo_location(), self._password, snapshot_id, target)

    def prune(self) -> None:
        self.restic.prune(
            self.repo_location(), self._password, keep_args_from_settings(self.settings)
        )

    def check(self) -> None:
        self.restic.check(self.repo_location(), self._password)

    def is_busy(self) -> bool:
        return self.restic.is_running() or self.rclone.is_running()

    # ------------------------------------------------------------------ signals
    def _on_restic_finished(self, success: bool, message: str) -> None:
        if self._initing_for_backup and self.restic._operation == "init":
            self._initing_for_backup = False
            if not success:
                self.operation_finished.emit("backup", False, message)
                return
            try:
                self.restic.backup(
                    self.repo_location(),
                    self._password,
                    self.settings.folders,
                    self._backup_excludes(),
                )
                return
            except Exception as exc:
                self.operation_finished.emit("backup", False, str(exc))
                return
        operation = self.restic._operation
        if operation == "check":
            self.check_finished.emit(success, message)
        else:
            self.operation_finished.emit(operation, success, message)

    def _on_snapshots(self, snapshots: list) -> None:
        self.snapshots_ready.emit(snapshots)

    def _on_files(self, nodes: list) -> None:
        self.files_ready.emit(nodes)

    def _on_remotes(self, remotes: list) -> None:
        self.remotes_ready.emit(remotes)
