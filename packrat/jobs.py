"""High-level backup orchestration used by the UI, tray and scheduler."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .backend import BackupBackend
from .notify import notify, notify_error
from .settings import Settings

log = logging.getLogger(__name__)


class BackupJob(QObject):
    """Tracks one backup run end-to-end and updates settings timestamps."""

    started = pyqtSignal()
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)

    def __init__(
        self,
        settings: Settings,
        backend: BackupBackend,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.backend = backend
        self._running = False
        backend.operation_finished.connect(self._on_operation_finished)
        backend.progress.connect(self.progress)

    def is_running(self) -> bool:
        return self._running or self.backend.is_busy()

    def start_backup(self) -> bool:
        if self.is_running():
            return False
        if not self.settings.folders:
            self.finished.emit(False, "No folders are selected to back up.")
            return False
        try:
            self._running = True
            self.started.emit()
            self.backend.run_backup()
            return True
        except Exception as exc:
            self._running = False
            log.exception("Backup failed to start")
            self.finished.emit(False, f"Backup failed to start: {exc}")
            return False

    def start_restore(self, snapshot_id: str, target: str) -> bool:
        if self.is_running():
            return False
        try:
            self._running = True
            self.started.emit()
            self.backend.restore_snapshot(snapshot_id, target)
            return True
        except Exception as exc:
            self._running = False
            self.finished.emit(False, f"Restore failed to start: {exc}")
            return False

    def _on_operation_finished(self, operation: str, success: bool, message: str) -> None:
        self._running = False
        if operation == "backup" and success:
            now = _dt.datetime.now()
            self.settings.last_backup_time = now.isoformat(timespec="seconds")
            self.settings.save()
            notify("Packrat Backup", "Backup finished successfully.")
        elif operation == "backup":
            notify_error("Packrat Backup", f"Backup failed: {message}")
        elif operation == "restore" and success:
            notify("Packrat Backup", "Restore finished successfully.")
        self.finished.emit(success, message)
