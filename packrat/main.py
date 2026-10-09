"""Main window: sidebar navigation and orchestration of all pages."""

from __future__ import annotations

import datetime as _dt
import logging
import os
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from . import APP_NAME
from .activity import log_run
from .backend import BackendError, BackupBackend
from .humanize import (
    backup_status,
    describe_future,
    describe_past,
    schedule_summary,
)
from .jobs import BackupJob
from .notify import notify_error
from .pages import (
    AboutPage,
    FoldersPage,
    HistoryPage,
    OverviewPage,
    PreferencesPage,
    RestorePage,
    SchedulePage,
    SnapshotBrowserDialog,
    StoragePage,
)
from .passwords import load_password, store_password
from .restic import ResticProcessError
from .scheduler import Scheduler, next_run_time
from .settings import ScheduleMode, Settings, update_autostart
from .tray import TrayController
from .widgets import SkippedFilesDialog

log = logging.getLogger(__name__)

_NAV = [
    ("Overview", "overview"),
    ("Folders", "folders"),
    ("Storage", "storage"),
    ("Schedule", "schedule"),
    ("Restore", "restore"),
    ("History", "history"),
    ("Preferences", "preferences"),
    ("About", "about"),
]


class MainWindow(QMainWindow):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self.backend = BackupBackend(self.settings, self)
        self.job = BackupJob(self.settings, self.backend, self)
        self.scheduler = Scheduler(self.settings.schedule, self)
        self._browser: Optional[SnapshotBrowserDialog] = None
        self._last_operation: str = ""
        self._snapshots_loaded_at: Optional[_dt.datetime] = None
        self._snapshots_loaded_after_backup: str = ""
        self._verify_pending: bool = False
        self._cleanup_after_stop: bool = False
        self.setWindowTitle(APP_NAME)
        self.resize(900, 640)

        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        for label, _key in _NAV:
            QListWidgetItem(label, self._nav)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        outer.addWidget(self._nav)

        self._stack = QStackedWidget()
        self.overview_page = OverviewPage()
        self.folders_page = FoldersPage()
        self.history_page = HistoryPage()
        self.storage_page = StoragePage(self.backend.rclone)
        self.schedule_page = SchedulePage()
        self.restore_page = RestorePage()
        self.preferences_page = PreferencesPage()
        self.about_page = AboutPage()
        for page in (
            self.overview_page,
            self.folders_page,
            self.storage_page,
            self.schedule_page,
            self.restore_page,
            self.history_page,
            self.preferences_page,
            self.about_page,
        ):
            self._stack.addWidget(page)
        outer.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self.overview_page.backup_requested.connect(self.start_backup)
        self.overview_page.stop_requested.connect(self._stop_backup)
        self.overview_page.restore_requested.connect(self._goto_restore)
        self.overview_page.verify_requested.connect(self.start_check)
        self.overview_page.preview_requested.connect(self.start_preview)
        self.folders_page.changed.connect(self._save_folders)
        self.storage_page.changed.connect(self._save_storage)
        self.schedule_page.changed.connect(self._save_schedule)
        self.schedule_page.clean_now_requested.connect(self.start_cleanup)
        self.history_page.refresh_requested.connect(self._refresh_history)
        self.restore_page.refresh_requested.connect(self.refresh_snapshots)
        self.restore_page.restore_requested.connect(self.start_restore)
        self.restore_page.browse_requested.connect(self._on_browse_snapshot)
        self.restore_page.cleanup_requested.connect(self._cleanup_incomplete)
        self.backend.restic.prune_stats_ready.connect(self._on_prune_stats)
        self.backend.files_ready.connect(self._on_files_ready)
        self.preferences_page.changed.connect(self._save_preferences)
        self.job.started.connect(self._on_job_started)
        self.job.finished.connect(self._on_job_finished)
        self.job.finished.connect(lambda *_: self._refresh_history())
        self.backend.operation_finished.connect(self._maybe_auto_cleanup)
        self.job.progress.connect(self._on_progress)
        self.backend.snapshots_ready.connect(self._on_snapshots_ready)
        self.backend.check_finished.connect(self._on_check_finished)
        self.backend.dry_run_ready.connect(self._on_dry_run_ready)
        self.backend.verify_finished.connect(self._on_verify_finished)
        self.backend.operation_finished.connect(self._on_operation_finished)
        self.scheduler.backup_due.connect(self.start_backup)

        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_and_raise)
        self.tray.backup_requested.connect(self.start_backup)
        self.tray.pause_toggled.connect(self._on_tray_pause)
        self.tray.on_quit(lambda: self._on_quit())
        self.tray.show()

        self._load_pages()
        self._refresh_overview()
        self._refresh_history()
        QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------ startup
    def _startup(self) -> None:
        if not self.settings.first_run_done:
            self._run_first_run_wizard()
        else:
            self._apply_password_from_store()
        self.scheduler.set_paused(self.settings.schedule_paused)
        self.scheduler.start()
        update_autostart(self.settings.run_at_startup)
        self._run_missed_backup_catchup()

    def _run_missed_backup_catchup(self) -> None:
        """Run a missed backup on launch (e.g. machine was asleep when due)."""
        if not self.settings.first_run_done:
            return
        if not self.settings.folders:
            return
        if self.job.is_running() or self.backend.is_busy():
            return
        last_dt = None
        if self.settings.last_backup_time:
            try:
                last_dt = _dt.datetime.fromisoformat(self.settings.last_backup_time)
            except ValueError:
                last_dt = None
        if not self.scheduler.missed_backup(last_dt):
            return
        log.info("Scheduled backup was missed while Packrat was not running")
        last_text = last_dt.strftime("%Y-%m-%d %H:%M") if last_dt else "never"
        answer = QMessageBox.question(
            self,
            "Packrat Backup",
            f"A scheduled backup was missed (last backup: {last_text}).\n\nStart it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            log.info("User declined catch-up backup")
            return
        self.start_backup()

    def _apply_password_from_store(self) -> None:
        password = load_password()
        if password:
            self.backend.set_password(password)

    def _run_first_run_wizard(self) -> None:
        from .wizard import FirstRunWizard

        wizard = FirstRunWizard(self.backend.rclone, self)
        wizard.finished_ok.connect(self._apply_wizard_result)
        wizard.show()

    def _apply_wizard_result(self, result: dict) -> None:
        settings = self.settings
        settings.folders = result["folders"]
        cfg = result["backend"]
        settings.backend_cfg.backend = cfg["backend"]
        settings.backend_cfg.local_path = cfg["local_path"]
        settings.backend_cfg.rclone_remote = cfg["rclone_remote"]
        settings.backend_cfg.rclone_path = cfg["rclone_path"]
        store_password(result["password"])
        self.backend.set_password(result["password"])
        settings.schedule.mode = ScheduleMode(result["schedule"])
        settings.first_run_done = True
        settings.save()
        self._load_pages()
        self._refresh_overview()
        self._refresh_history()
        try:
            self.backend.init_repository()
        except (BackendError, ResticProcessError) as exc:
            QMessageBox.warning(self, "Packrat Backup", f"Could not prepare repository: {exc}")

    # ------------------------------------------------------------------ pages
    def _load_pages(self) -> None:
        self.folders_page.load(
            self.settings.folders, self.settings.exclude_patterns, self.settings.ignored_folders
        )
        self.storage_page.load(self.settings.backend_cfg)
        self.storage_page.set_remote_name(self.settings.backend_cfg.rclone_remote)
        self.schedule_page.load(
            self.settings.schedule,
            paused=self.settings.schedule_paused,
            settings=self.settings,
        )
        self.preferences_page.load(self.settings)
        self._nav.setCurrentRow(0)

    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)
        if row == 4:
            self.show_snapshots()
        elif row == 5:
            self._refresh_history()

    def _goto_restore(self) -> None:
        self._nav.setCurrentRow(4)

    # ------------------------------------------------------------------ saving
    def _save_folders(self) -> None:
        folders, excludes, ignored = self.folders_page.save()
        self.settings.folders = folders
        self.settings.exclude_patterns = excludes
        self.settings.ignored_folders = ignored
        self.settings.save()
        self._refresh_overview()

    def _save_storage(self) -> None:
        data = self.storage_page.save()
        self.settings.backend_cfg.backend = data["backend"]
        self.settings.backend_cfg.local_path = data["local_path"]
        self.settings.backend_cfg.rclone_remote = data["rclone_remote"]
        self.settings.backend_cfg.rclone_path = data["rclone_path"]
        self.settings.save()
        self._refresh_overview()

    def _save_schedule(self) -> None:
        data = self.schedule_page.save()
        self.settings.schedule.mode = data["mode"]
        self.settings.schedule.time = data["time"]
        self.settings.schedule.weekdays = data["weekdays"]
        self.settings.schedule_paused = data["paused"]
        self.settings.keep_daily = data["keep_daily"]
        self.settings.keep_weekly = data["keep_weekly"]
        self.settings.keep_monthly = data["keep_monthly"]
        self.settings.keep_yearly = data["keep_yearly"]
        self.settings.auto_prune = data["auto_prune"]
        self.settings.auto_prune_interval_days = data["auto_prune_interval_days"]
        self.settings.save()
        self.scheduler.set_paused(self.settings.schedule_paused)
        self.tray.set_pause_state(self.settings.schedule_paused)
        self.scheduler.recompute()
        self._refresh_overview()

    def _save_preferences(self) -> None:
        data = self.preferences_page.save()
        self.settings.close_to_tray = data["close_to_tray"]
        self.settings.run_at_startup = data["run_at_startup"]
        self.settings.restore_refresh_minutes = data["restore_refresh_minutes"]
        self.settings.cloud_connections = data["cloud_connections"]
        self.settings.cloud_pack_size = data["cloud_pack_size"]
        self.settings.verify_after_backup = data["verify_after_backup"]
        self.settings.change_detection = data["change_detection"]
        self.settings.changed_files_threshold = data["changed_files_threshold"]
        self.settings.save()
        update_autostart(self.settings.run_at_startup)

    # ------------------------------------------------------------------ actions
    def start_backup(self) -> None:
        if self.job.is_running():
            return
        if not self.settings.folders:
            QMessageBox.information(
                self, "Packrat Backup", "Choose at least one folder to back up first."
            )
            return
        if not load_password() and not self.backend.has_password():
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "No backup password is stored. Please complete the first-run setup.",
            )
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        try:
            self.job.start_backup()
        except BackendError as exc:
            QMessageBox.warning(self, "Packrat Backup", str(exc))

    def start_preview(self) -> None:
        """Dry-run the next backup and show an estimate (#19)."""
        if self.backend.is_busy():
            return
        if not self.settings.folders:
            QMessageBox.information(
                self, "Packrat Backup", "Choose at least one folder to back up first."
            )
            return
        if not load_password() and not self.backend.has_password():
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "No backup password is stored. Please complete the first-run setup.",
            )
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        try:
            self.overview_page.set_previewing(True)
            self.overview_page.clear_preview()
            self.backend.preview_backup()
        except (BackendError, ResticProcessError) as exc:
            self.overview_page.set_previewing(False)
            QMessageBox.warning(self, "Packrat Backup", f"Could not preview the backup: {exc}")

    def _on_dry_run_ready(self, summary: dict) -> None:
        self.overview_page.set_previewing(False)
        self.overview_page.set_preview_result(summary)

    def start_check(self) -> None:
        if self.backend.is_busy():
            return
        if not self.backend.is_configured():
            QMessageBox.information(self, "Packrat Backup", "Choose a backup destination first.")
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "No backup password is stored; cannot verify the repository.",
            )
            return
        try:
            self.overview_page.set_checking(True)
            self.overview_page.clear_progress()
            self.backend.check()
        except (BackendError, ResticProcessError) as exc:
            self.overview_page.set_checking(False)
            QMessageBox.warning(self, "Packrat Backup", str(exc))

    def _on_check_finished(self, success: bool, message: str) -> None:
        self.overview_page.set_checking(False)
        self.overview_page.clear_progress()
        log_run("check", success, message, _dt.datetime.now().isoformat(timespec="seconds"))
        self.settings.last_verified_time = _dt.datetime.now().isoformat(timespec="seconds")
        self.settings.last_verified_ok = success
        self.settings.last_verified_snapshot_id = self.backend.last_snapshot_id
        self.settings.save()
        self._refresh_overview()
        self.history_page.refresh()
        if success:
            self.tray.show_message("Packrat Backup", "Repository verification succeeded.")
            QMessageBox.information(
                self, "Packrat Backup", f"Repository integrity check passed.\n\n{message}"
            )
        else:
            self.tray.show_message("Packrat Backup", "Repository verification failed!")
            QMessageBox.warning(
                self, "Packrat Backup", f"Repository integrity check failed:\n\n{message}"
            )

    def start_restore(self, snapshot_id: str, target: str, includes=None) -> None:
        if self.job.is_running():
            return
        if not snapshot_id or not target:
            QMessageBox.information(
                self, "Packrat Backup", "Select a snapshot and a destination folder."
            )
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            QMessageBox.warning(
                self, "Packrat Backup", "No backup password is stored; cannot restore."
            )
            return
        self.job.start_restore(snapshot_id, target, includes)

    def _on_restore_selected(self, paths: list) -> None:
        """Partial restore from the snapshot browser (issue #16)."""
        browser = self._browser
        if browser is None or not paths:
            return
        if self.job.is_running():
            QMessageBox.information(
                self, "Packrat Backup", "A backup or restore is already running."
            )
            return
        target = QFileDialog.getExistingDirectory(
            self,
            f"Restore {len(paths)} item{'s' if len(paths) != 1 else ''} into folder",
            os.path.expanduser("~"),
        )
        if not target:
            return
        snapshot_id = browser.snapshot_id()
        browser.done(QDialog.DialogCode.Rejected)
        self.start_restore(snapshot_id, target, includes=paths)

    def show_snapshots(self) -> None:
        """Show the Restore page, reloading only when the cache is stale."""
        if self._snapshots_cache_valid():
            return
        self.refresh_snapshots()

    def _snapshots_cache_valid(self) -> bool:
        if self._snapshots_loaded_at is None:
            return False
        minutes = self.settings.restore_refresh_minutes
        if minutes <= 0:
            return False
        age = (_dt.datetime.now() - self._snapshots_loaded_at).total_seconds() / 60
        if age >= minutes:
            return False
        if self.settings.last_backup_time != self._snapshots_loaded_after_backup:
            return False
        return True

    def refresh_snapshots(self) -> None:
        if self.backend.is_busy():
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            return
        try:
            self.restore_page.set_loading(True)
            self.backend.list_snapshots()
        except (BackendError, ResticProcessError) as exc:
            self.restore_page.set_loading(False)
            log.warning("Cannot list snapshots: %s", exc)

    def _on_snapshots_ready(self, snapshots) -> None:
        self.restore_page.set_loading(False)
        self.restore_page.set_snapshots(snapshots)
        self._snapshots_loaded_at = _dt.datetime.now()
        self._snapshots_loaded_after_backup = self.settings.last_backup_time
        self._adopt_newest_snapshot_time(snapshots)

    @staticmethod
    def _trim_iso_nanos(raw: str) -> str:
        """Normalise a restic timestamp for datetime.fromisoformat.

        restic emits nanosecond precision ("...42.533518173Z"); Python
        3.10 rejects anything beyond microseconds, so trim to 6 digits
        and make the trailing Z explicit.
        """
        import re

        match = re.match(r"^(.*?\.\d{6})\d*(Z|[+-]\d{2}:?\d{2})?$", raw)
        if match:
            raw = match.group(1) + (match.group(2) or "")
        return raw.replace("Z", "+00:00")

    def _adopt_newest_snapshot_time(self, snapshots) -> None:
        """Reconcile last_backup_time with the newest snapshot.

        A backup can save a snapshot even when Packrat records it as a
        failure (e.g. pre-fix exit-3 runs); the Overview badge would then
        claim "overdue" while the repository provably has a fresh
        snapshot. When the newest snapshot is newer than the recorded
        last backup, adopt it.
        """
        newest = None
        for snap in snapshots:
            raw = str((snap or {}).get("time") or "")
            try:
                when = _dt.datetime.fromisoformat(self._trim_iso_nanos(raw))
            except ValueError:
                continue
            if when.tzinfo is not None:
                when = when.astimezone().replace(tzinfo=None)
            if newest is None or when > newest:
                newest = when
        if newest is None:
            return
        recorded = None
        if self.settings.last_backup_time:
            try:
                recorded = _dt.datetime.fromisoformat(self.settings.last_backup_time)
            except ValueError:
                recorded = None
        if recorded is None or newest > recorded:
            self.settings.last_backup_time = newest.isoformat(timespec="seconds")
            self.settings.save()
            self._refresh_overview()

    def _maybe_auto_cleanup(self, operation: str, success: bool, _message: str) -> None:
        """Apply retention after a backup: forget every run, prune on a schedule (#64)."""
        if operation != "backup" or not success:
            return
        self._verify_pending = self.settings.verify_after_backup != "off"
        if not self.settings.auto_prune:
            self._maybe_start_verification()
            return
        if self.job.is_running():
            return
        if not self.backend.has_password():
            return
        if not self.backend.prune_due():
            log.debug("Auto-prune: not due yet, only applying retention")
            if self.job.start_forget():
                self.schedule_page.set_cleaning(True)
                self.tray.set_state(running=True, status_text="Cleaning up…")
                return
            self._maybe_start_verification()
            return
        log.info("Auto-prune: cleaning up after successful backup")
        if self.job.start_prune_orphans():
            self.schedule_page.set_cleaning(True)
            self.tray.set_state(running=True, status_text="Cleaning up…")
            return
        self._maybe_start_verification()

    def _maybe_start_verification(self) -> None:
        """Run the post-backup restorability proof once nothing else is running (#28)."""
        if not self._verify_pending:
            return
        self._verify_pending = False
        if self.job.is_running() or self.backend.is_busy():
            return
        if not self.backend.has_password():
            return
        log.info("Verified restores: checking the fresh backup")
        self.tray.set_state(running=True, status_text="Verifying backup…")
        try:
            self.backend.verify_backup()
        except (BackendError, ResticProcessError) as exc:
            log.warning("Could not verify backup: %s", exc)
            self.tray.set_state(running=False, status_text="Packrat Backup")

    def _on_verify_finished(self, success: bool, message: str) -> None:
        self.settings.last_verified_time = _dt.datetime.now().isoformat(timespec="seconds")
        self.settings.last_verified_ok = success
        self.settings.last_verified_snapshot_id = self.backend.last_snapshot_id
        self.settings.save()
        log_run(
            "verify",
            success,
            message,
            self.settings.last_verified_time,
            snapshot_id=self.settings.last_verified_snapshot_id,
        )
        self.history_page.refresh()
        self.tray.set_state(running=False, status_text="Packrat Backup")
        self._refresh_overview()
        if success:
            self.tray.show_message(
                "Packrat Backup", "Backup verified: the repository is restorable."
            )
        else:
            notify_error("Packrat Backup", f"Backup verification FAILED: {message}")
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "Packrat could not prove the latest backup restorable.\n\n"
                "The backup data may be damaged; consider checking your "
                f"destination.\n\n{message}",
            )

    def _on_operation_finished(self, operation: str, success: bool, message: str) -> None:
        self._last_operation = operation
        if operation == "dry-run":
            self.overview_page.set_previewing(False)
            if not success:
                self.overview_page.clear_preview()
                QMessageBox.warning(self, "Packrat Backup", f"Backup preview failed: {message}")
            return
        if operation == "snapshots" and not success:
            self.restore_page.set_loading(False)
        elif operation == "ls" and not success:
            if self._browser is not None:
                self._browser.set_error(f"Could not list snapshot contents: {message}")

    def _on_browse_snapshot(self, snapshot_id: str, snapshot_time: str) -> None:
        if self.backend.is_busy():
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            QMessageBox.warning(
                self, "Packrat Backup", "No backup password is stored; cannot browse snapshots."
            )
            return
        self._browser = SnapshotBrowserDialog(snapshot_id, snapshot_time, self)
        self._browser.closed.connect(self._on_browser_closed)
        self._browser.restore_selected_requested.connect(self._on_restore_selected)
        self._browser.set_loading(True)
        self._browser.open()
        try:
            self.backend.list_snapshot_files(snapshot_id)
        except (BackendError, ResticProcessError) as exc:
            self._browser.set_error(f"Could not list snapshot contents: {exc}")

    def _on_files_ready(self, nodes) -> None:
        if self._browser is not None:
            self._browser.set_nodes(nodes)

    def _on_browser_closed(self) -> None:
        sender = self.sender()
        if sender is self._browser:
            self._browser = None

    # ------------------------------------------------------------------ events
    def _on_job_started(self) -> None:
        self.overview_page.clear_progress()
        self.restore_page.clear_restore_progress()
        if self.job._starting_operation == "backup":
            self.overview_page.set_backup_running(True)
            self.restore_page.set_enabled_state(True)
            self.tray.set_state(running=True, status_text="Backup running…")
            self._refresh_overview(running=True)
        else:
            self.overview_page.set_backup_running(False)
            self.overview_page.set_backup_enabled(False)

    def _stop_backup(self) -> None:
        """Stop the running backup cleanly (#63).

        A stopped backup leaves unreferenced data in the repository (the
        packs uploaded so far, plus a stale lock). The user asked for the
        backup to stop, not for the leftover data to stay forever, so after
        the process dies we automatically unlock and prune the orphans.
        """
        if not self.job.is_running():
            return
        log.info("Stop requested by user")
        self._cleanup_after_stop = True
        self.overview_page.set_progress(-1, "Stopping…")
        self.backend.restic.stop()

    def _cleanup_incomplete(self) -> None:
        """Remove partial data left by interrupted backups (#63)."""
        if self.job.is_running():
            QMessageBox.information(
                self, "Packrat Backup", "Wait for the running operation to finish first."
            )
            return
        if not self.backend.is_configured():
            QMessageBox.information(self, "Packrat Backup", "Choose a backup destination first.")
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "No backup password is stored; cannot clean up the repository.",
            )
            return
        if self.backend.has_snapshots():
            confirm = QMessageBox.question(
                self,
                "Packrat Backup",
                "Remove leftover data from interrupted backups and free its space?\n"
                "This never touches data belonging to your saved snapshots.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            if not self.job.start_prune_orphans():
                self.restore_page.set_cleaning_up(False)
                QMessageBox.information(
                    self, "Packrat Backup", "A backup or cleanup is already running."
                )
                return
            self.restore_page.set_cleaning_up(True)
            self.tray.set_state(running=True, status_text="Cleaning up…")
            return
        confirm = QMessageBox.question(
            self,
            "Packrat Backup",
            "This repository has no snapshots — all data in it is leftover from interrupted backups.\n\n"
            "Delete the entire repository and recreate it empty?\n"
            "This is the fastest way to free the space and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._reset_repository()

    def _reset_repository(self) -> None:
        """Purge and re-init a snapshot-less repository, off the UI thread."""
        import threading

        self.restore_page.set_cleaning_up(True)
        self.tray.set_state(running=True, status_text="Resetting repository…")

        def worker() -> None:
            ok, detail = self.backend.reset_repository_sync()

            def deliver() -> None:
                self.restore_page.set_cleaning_up(False)
                self.tray.set_state(running=False, status_text="Packrat Backup")
                if ok:
                    log.info("Repository reset: purged and re-initialised")
                    self.backend._snapshot_count = None
                    self.tray.show_message(
                        "Packrat Backup", "Repository reset. All leftover data was deleted."
                    )
                else:
                    log.warning("Repository reset failed: %s", detail)
                    QMessageBox.warning(
                        self, "Packrat Backup", f"Repository reset failed: {detail}"
                    )

            QTimer.singleShot(0, deliver)

        threading.Thread(target=worker, daemon=True).start()

    def _on_prune_stats(self, stats: dict) -> None:
        self.restore_page.set_cleaning_up(False)
        self.restore_page.set_cleanup_result(int(stats.get("blobs", 0)), int(stats.get("bytes", 0)))
        self.tray.set_state(running=False, status_text="Packrat Backup")
        ok, detail = self.backend.delete_interrupted_tmp_files()
        if not ok:
            log.warning("Failed to remove interrupted-upload tmp files: %s", detail)
        elif detail:
            log.info("Removed interrupted-upload tmp files")

    def _on_progress(self, percent: int, message: str) -> None:
        if self.backend.restic._operation == "restore":
            self.restore_page.set_restore_progress(percent, message)
            return
        if self.backend.restic._operation == "prune":
            self.overview_page.set_progress(percent, message)
            return
        if self.backend.restic._operation == "check":
            self.overview_page.set_progress(percent, message)
            return
        if self.backend.restic._operation == "dry-run":
            self.overview_page.set_progress(percent, f"Previewing backup — {message}")
            return
        self.overview_page.set_progress(percent, message)
        if percent >= 0:
            self.tray.set_state(running=True, status_text=f"Backup {percent}%")

    def _start_post_stop_cleanup(self) -> None:
        """Unlock and prune the data a stopped backup leaves behind.

        Runs only when a backup was stopped by the user; a normally finished
        backup references everything it uploaded, so there is nothing to do.
        """
        if not self._cleanup_after_stop:
            return
        self._cleanup_after_stop = False
        if not self.backend.is_configured() or not self.backend.has_password():
            return
        ok, detail = self.backend.remove_stale_lock()
        if not ok:
            log.warning("Post-stop unlock failed: %s", detail)
            return
        if self.job.start_prune_orphans():
            log.info("Cleaning up data left by the stopped backup")
            self.overview_page.set_progress(-1, "Cleaning up after stop…")
            self.tray.set_state(running=True, status_text="Cleaning up…")

    def _on_job_finished(self, success: bool, message: str) -> None:
        self.overview_page.set_backup_running(False)
        if self.job.last_operation in ("prune", "forget"):
            self._on_cleanup_finished(success, message)
            return
        self.overview_page.set_backup_enabled(True)
        self.overview_page.clear_progress()
        self.restore_page.set_enabled_state(False)
        self.restore_page.clear_restore_progress()
        self._refresh_overview()
        self.tray.set_state(running=False, status_text="Packrat Backup")
        if message == "Stopped by user.":
            self.tray.show_message("Packrat Backup", "Backup stopped. Saved snapshots are safe.")
            self._start_post_stop_cleanup()
            return
        skipped = self.backend.restic.unreadable_files
        if "could not be read" in message and skipped:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning if not success else QMessageBox.Icon.Information)
            box.setWindowTitle("Packrat Backup")
            box.setText(message)
            box.setInformativeText(
                f"{len(skipped)} file{'s' if len(skipped) != 1 else ''} could not be read."
            )
            details_button = box.addButton("Details…", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Close)
            box.exec()
            if box.clickedButton() is details_button:
                SkippedFilesDialog(skipped, self).exec()
            return
        if not success:
            QMessageBox.warning(self, "Packrat Backup", message)
        else:
            self.tray.show_message("Packrat Backup", message)

    def start_cleanup(self) -> None:
        """Run a manual cleanup (restic forget --prune) using the retention policy."""
        if self.job.is_running():
            QMessageBox.information(
                self, "Packrat Backup", "A backup or cleanup is already running."
            )
            return
        if not self.backend.is_configured():
            QMessageBox.information(self, "Packrat Backup", "Choose a backup destination first.")
            return
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            QMessageBox.warning(
                self,
                "Packrat Backup",
                "No backup password is stored; cannot clean up the repository.",
            )
            return
        if self.backend.has_snapshots():
            started = self.job.start_prune()
        else:
            started = self.job.start_prune_orphans()
        if started:
            self.schedule_page.set_cleaning(True)
            self.overview_page.set_backup_enabled(False)
            self.tray.set_state(running=True, status_text="Cleaning up…")

    def _on_cleanup_finished(self, success: bool, message: str) -> None:
        if self.job.last_operation == "prune" and success:
            self.settings.last_prune_time = _dt.datetime.now().isoformat(timespec="seconds")
            self.settings.save()
        self.restore_page.set_cleaning_up(False)
        self.schedule_page.set_cleaning(False)
        self.overview_page.set_backup_enabled(True)
        self._refresh_overview()
        self.tray.set_state(running=False, status_text="Packrat Backup")
        self._maybe_start_verification()
        if success:
            self.tray.show_message("Packrat Backup", "Cleanup finished successfully.")
            return
        if "unlock" in message.lower() or "unable to create lock" in message.lower():
            answer = QMessageBox.question(
                self,
                "Packrat Backup",
                f"Cleanup failed because the repository is locked by an interrupted run:\n{message}\n\nRemove the stale lock and retry the cleanup?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            ok, detail = self.backend.remove_stale_lock()
            if not ok:
                QMessageBox.warning(self, "Packrat Backup", f"Unlock failed: {detail}")
                return
            log.info("Stale lock removed; retrying cleanup")
            if self.job.last_operation == "prune":
                self.start_cleanup()
            else:
                self._cleanup_incomplete()
            return
        QMessageBox.warning(self, "Packrat Backup", f"Cleanup failed: {message}")

    def _refresh_history(self) -> None:
        self.history_page.refresh()

    def _on_tray_pause(self, paused: bool) -> None:
        self.scheduler.set_paused(paused)
        self.settings.schedule_paused = paused
        self.settings.save()
        self.schedule_page.load(self.settings.schedule, paused=paused)
        self._refresh_overview()

    def _refresh_overview(self, running: bool = False) -> None:
        last_dt = None
        if self.settings.last_backup_time:
            try:
                last_dt = _dt.datetime.fromisoformat(self.settings.last_backup_time)
            except ValueError:
                last_dt = None
        last_text = describe_past(last_dt)
        nxt = next_run_time(self.settings.schedule)
        next_text = describe_future(nxt) if not running else "—"
        schedule_text = schedule_summary(
            self.settings.schedule.mode,
            self.settings.schedule.time,
            self.settings.schedule.weekdays,
        )
        try:
            destination = self.settings.backend_summary()
        except Exception:
            destination = "not configured"
        verified_dt = None
        if self.settings.last_verified_time:
            try:
                verified_dt = _dt.datetime.fromisoformat(self.settings.last_verified_time)
            except ValueError:
                verified_dt = None
        if verified_dt is None:
            verified_text = "never"
        elif not self.settings.last_verified_ok:
            verified_text = f"failed {describe_past(verified_dt)}"
        else:
            verified_text = describe_past(verified_dt)
        status = backup_status(
            last_dt,
            nxt if not running else None,
            paused=self.scheduler.is_paused(),
        )
        if self.settings.last_change_status == "suspicious":
            status = {"state": "error", "label": "Unusual changes detected!"}
        self.overview_page.set_state(
            last_text,
            next_text,
            destination,
            running,
            schedule=schedule_text,
            badge_state=status["state"],
            badge_label=status["label"],
            verified=verified_text,
            change_status=self.settings.last_change_status,
        )
        self.tray.set_state(
            running=running,
            paused=self.scheduler.is_paused(),
            status_text="Backup running…" if running else "Packrat Backup",
        )

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        # An exception escaping a Qt event handler crashes the whole app on
        # exit (observed as a SEGV inside CPython's traceback printing on
        # Python 3.14). Close/quit must never take the app down.
        try:
            self._handle_close(event)
        except Exception:
            log.exception("closeEvent failed")
            if event is not None:
                event.accept()
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _handle_close(self, event) -> None:
        if not self.settings.close_to_tray:
            self._quit_app(event)
            return
        event.ignore()
        self.hide()
        self.tray.show_message(
            "Packrat Backup",
            "Packrat keeps running in the tray. Right-click the tray icon to quit.",
        )

    def _quit_app(self, event=None) -> None:
        if self.job.is_running():
            answer = QMessageBox.question(
                self,
                "Backup in progress",
                "A backup or restore is still running. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                if event is not None:
                    event.ignore()
                return
        if event is not None:
            event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_quit(self) -> None:
        self._quit_app()
