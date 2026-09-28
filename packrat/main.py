"""Main window: sidebar navigation and orchestration of all pages."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from . import APP_NAME
from .backend import BackendError, BackupBackend
from .jobs import BackupJob
from .pages import (
    AboutPage,
    FoldersPage,
    OverviewPage,
    PreferencesPage,
    RestorePage,
    SchedulePage,
    StoragePage,
)
from .passwords import load_password, store_password
from .scheduler import Scheduler, next_run_time
from .settings import ScheduleMode, Settings, update_autostart
from .tray import TrayController

log = logging.getLogger(__name__)

_NAV = [
    ("Overview", "overview"),
    ("Folders", "folders"),
    ("Storage", "storage"),
    ("Schedule", "schedule"),
    ("Restore", "restore"),
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
            self.preferences_page,
            self.about_page,
        ):
            self._stack.addWidget(page)
        outer.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self.overview_page.backup_requested.connect(self.start_backup)
        self.overview_page.restore_requested.connect(self._goto_restore)
        self.folders_page.changed.connect(self._save_folders)
        self.storage_page.changed.connect(self._save_storage)
        self.schedule_page.changed.connect(self._save_schedule)
        self.restore_page.refresh_requested.connect(self.refresh_snapshots)
        self.restore_page.restore_requested.connect(self.start_restore)
        self.preferences_page.changed.connect(self._save_preferences)
        self.job.started.connect(self._on_backup_started)
        self.job.finished.connect(self._on_job_finished)
        self.job.progress.connect(self._on_progress)
        self.backend.snapshots_ready.connect(self.restore_page.set_snapshots)
        self.backend.restic.snapshots_listed.connect(self.restore_page.set_snapshots)
        self.scheduler.backup_due.connect(self.start_backup)

        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_and_raise)
        self.tray.backup_requested.connect(self.start_backup)
        self.tray.pause_toggled.connect(self._on_tray_pause)
        self.tray.on_quit(lambda: self._on_quit())
        self.tray.show()

        self._load_pages()
        self._refresh_overview()
        QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------ startup
    def _startup(self) -> None:
        if not self.settings.first_run_done:
            self._run_first_run_wizard()
        else:
            self._apply_password_from_store()
        self.scheduler.start()
        update_autostart(self.settings.run_at_startup)

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
        try:
            self.backend.init_repository()
        except BackendError as exc:
            QMessageBox.warning(self, "Packrat Backup", f"Could not prepare repository: {exc}")

    # ------------------------------------------------------------------ pages
    def _load_pages(self) -> None:
        self.folders_page.load(self.settings.folders, self.settings.exclude_patterns)
        self.storage_page.load(self.settings.backend_cfg)
        self.storage_page.set_remote_name(self.settings.backend_cfg.rclone_remote)
        self.schedule_page.load(self.settings.schedule)
        self.preferences_page.load(self.settings)
        self._nav.setCurrentRow(0)

    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)
        if row == 4:
            self.refresh_snapshots()

    def _goto_restore(self) -> None:
        self._nav.setCurrentRow(4)

    # ------------------------------------------------------------------ saving
    def _save_folders(self) -> None:
        folders, excludes = self.folders_page.save()
        self.settings.folders = folders
        self.settings.exclude_patterns = excludes
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
        self.settings.save()
        self.scheduler.recompute()
        self._refresh_overview()

    def _save_preferences(self) -> None:
        data = self.preferences_page.save()
        self.settings.close_to_tray = data["close_to_tray"]
        self.settings.run_at_startup = data["run_at_startup"]
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

    def start_restore(self, snapshot_id: str, target: str) -> None:
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
        self.job.start_restore(snapshot_id, target)

    def refresh_snapshots(self) -> None:
        if not self.backend.has_password():
            self._apply_password_from_store()
        if not self.backend.has_password():
            return
        try:
            self.backend.list_snapshots()
        except BackendError as exc:
            log.warning("Cannot list snapshots: %s", exc)

    # ------------------------------------------------------------------ events
    def _on_backup_started(self) -> None:
        self.overview_page.set_backup_enabled(False)
        self.overview_page.clear_progress()
        self.tray.set_state(running=True, status_text="Backup running…")
        self._refresh_overview(running=True)

    def _on_progress(self, percent: int, message: str) -> None:
        self.overview_page.set_progress(percent, message)
        if percent >= 0:
            self.tray.set_state(running=True, status_text=f"Backup {percent}%")

    def _on_job_finished(self, success: bool, message: str) -> None:
        self.overview_page.set_backup_enabled(True)
        self.overview_page.clear_progress()
        self._refresh_overview()
        self.tray.set_state(running=False, status_text="Packrat Backup")
        if not success:
            QMessageBox.warning(self, "Packrat Backup", message)
        else:
            self.tray.show_message("Packrat Backup", message)

    def _on_tray_pause(self, paused: bool) -> None:
        self.scheduler.set_paused(paused)
        self._refresh_overview()

    def _refresh_overview(self, running: bool = False) -> None:
        last = self.settings.last_backup_time
        try:
            last_text = _dt.datetime.fromisoformat(last).strftime("%Y-%m-%d %H:%M") if last else ""
        except ValueError:
            last_text = last
        nxt = next_run_time(self.settings.schedule)
        next_text = nxt.strftime("%Y-%m-%d %H:%M") if nxt else ""
        try:
            destination = self.settings.backend_summary()
        except Exception:
            destination = "not configured"
        self.overview_page.set_state(last_text, next_text, destination, running)
        self.tray.set_state(
            running=running,
            paused=False,
            status_text="Backup running…" if running else "Packrat Backup",
        )

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
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
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().quit()

    def _on_quit(self) -> None:
        self._quit_app()
