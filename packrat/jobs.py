"""High-level backup orchestration used by the UI, tray and scheduler."""

from __future__ import annotations

import datetime as _dt
import logging
import time
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .activity import log_run
from .backend import BackupBackend
from .change_detect import analyze_summary, record_result
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
        self.last_operation: str = ""
        self._starting_operation: str = ""
        self._started_at: Optional[str] = ""
        self._started_monotonic = 0.0
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
        self._starting_operation = "backup"
        try:
            self._running = True
            self._started_at = _dt.datetime.now().isoformat(timespec="seconds")
            self._started_monotonic = time.monotonic()
            self.started.emit()
            self.backend.run_backup()
            return True
        except Exception as exc:
            self._running = False
            log.exception("Backup failed to start")
            self.finished.emit(False, f"Backup failed to start: {exc}")
            return False

    def start_restore(self, snapshot_id: str, target: str, includes=None) -> bool:
        if self.is_running():
            return False
        self._starting_operation = "restore"
        try:
            self._running = True
            self._started_at = _dt.datetime.now().isoformat(timespec="seconds")
            self._started_monotonic = time.monotonic()
            self.started.emit()
            self.backend.restore_snapshot(snapshot_id, target, includes)
            return True
        except Exception as exc:
            self._running = False
            self.finished.emit(False, f"Restore failed to start: {exc}")
            return False

    def start_prune(self) -> bool:
        return self._start_retention(self.backend.prune)

    def start_forget(self) -> bool:
        """Apply retention without repacking — cheap on cloud repositories (#64)."""
        return self._start_retention(self.backend.forget)

    def _start_retention(self, starter) -> bool:
        if self.is_running():
            return False
        self._starting_operation = "retention"
        try:
            self._running = True
            self._started_at = _dt.datetime.now().isoformat(timespec="seconds")
            self._started_monotonic = time.monotonic()
            starter()
            return True
        except Exception as exc:
            self._running = False
            log.exception("Cleanup failed to start")
            self.finished.emit(False, f"Cleanup failed to start: {exc}")
            return False

    def _on_operation_finished(self, operation: str, success: bool, message: str) -> None:
        self._running = False
        self.last_operation = operation
        if operation in ("backup", "restore", "prune", "forget"):
            log_run(
                operation,
                success,
                message,
                self._started_at,
                time.monotonic() - self._started_monotonic,
                snapshot_id=self.backend.last_snapshot_id if operation == "backup" else None,
            )
        if operation == "backup" and success:
            now = _dt.datetime.now()
            self.settings.last_backup_time = now.isoformat(timespec="seconds")
            self._analyze_changes()
            self.settings.save()
            notify("Packrat Backup", "Backup finished successfully.")
        elif operation == "backup" and message != "Stopped by user.":
            notify_error("Packrat Backup", f"Backup failed: {message}")
        elif operation == "restore" and success:
            notify("Packrat Backup", "Restore finished successfully.")
        self.finished.emit(success, message)

    def _analyze_changes(self) -> None:
        """Post-backup mass-change detection (issue #29)."""
        if not self.settings.change_detection:
            return
        summary = getattr(self.backend.restic, "last_backup_summary", {})
        try:
            report = analyze_summary(summary, float(self.settings.changed_files_threshold))
        except Exception:
            log.exception("Change analysis failed")
            return
        record_result(report, snapshot_id=self.backend.last_snapshot_id)
        self.settings.last_change_status = report.status
        log_run(
            "change-check",
            report.status != "suspicious",
            report.reason
            or f"{report.changed_files} of {report.total_files} files changed "
            f"({report.changed_files_ratio:.0f}%)",
            _dt.datetime.now().isoformat(timespec="seconds"),
        )
        if report.status == "suspicious":
            notify_error("Packrat Backup", f"Unusual changes detected! {report.reason}")
