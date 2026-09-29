"""Unified backup backend: local folders or rclone remotes.

Translates the user's settings into a restic repository location and
exposes high-level operations used by the UI and the scheduler.
"""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .rclone import RcloneRunner
from .restic import ResticRunner, keep_args_from_settings
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

    def _backup_excludes(self) -> list:
        excludes = list(self.settings.exclude_patterns)
        excludes.extend(os.path.expanduser(f) for f in self.settings.ignored_folders)
        return excludes
        self.restic.snapshots_listed.connect(self._on_snapshots)
        self.restic.files_listed.connect(self._on_files)
        self.rclone.remotes_listed.connect(self._on_remotes)

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
        return f"rclone:{remote}:{sub}" if sub else f"rclone:{remote}:"

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
        import os

        cfg = self.settings.backend_cfg
        if cfg.backend is Backend.LOCAL:
            path = os.path.expanduser(cfg.local_path)
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
