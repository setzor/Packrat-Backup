"""System tray presence: status icon, quick backup and pause scheduling."""

from __future__ import annotations

import logging
from importlib.resources import files
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from . import APP_ID

log = logging.getLogger(__name__)


def _default_icon() -> QIcon:
    """The Packrat mascot: themed icon first, bundled SVG as fallback."""
    icon = QIcon.fromTheme(APP_ID)
    if not icon.isNull():
        return icon
    return QIcon(str(files("packrat").joinpath("assets", "packrat-mascot.svg")))


class TrayController(QObject):
    open_requested = pyqtSignal()
    backup_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.icon = QSystemTrayIcon()
        self.icon.setIcon(_default_icon())
        self._icon_path: Optional[str] = None
        menu = QMenu()
        self._open_action = QAction("Open Packrat", self)
        self._open_action.triggered.connect(self.open_requested.emit)
        self._backup_action = QAction("Back up now", self)
        self._backup_action.triggered.connect(self.backup_requested.emit)
        self._pause_action = QAction("Pause scheduled backups", self)
        self._pause_action.setCheckable(True)
        self._pause_action.toggled.connect(self.pause_toggled.emit)
        self._quit_action = QAction("Quit", self)
        self._quit_action.triggered.connect(self._on_quit)
        menu.addAction(self._open_action)
        menu.addAction(self._backup_action)
        menu.addSeparator()
        menu.addAction(self._pause_action)
        menu.addSeparator()
        menu.addAction(self._quit_action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._on_activated)
        self._menu = menu
        self._quit_handlers = []

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()

    def _on_quit(self) -> None:
        for handler in self._quit_handlers:
            try:
                handler()
            except Exception:
                log.exception("Quit handler failed")

    def on_quit(self, handler) -> None:
        self._quit_handlers.append(handler)

    def show(self) -> None:
        self.icon.show()

    def hide(self) -> None:
        self.icon.hide()

    def set_icon_path(self, path: str) -> None:
        import os

        if path and os.path.isfile(path):
            self.icon.setIcon(QIcon(path))

    def set_state(
        self,
        running: bool = False,
        paused: bool = False,
        status_text: str = "Packrat Backup",
    ) -> None:
        self._backup_action.setEnabled(not running)
        self._pause_action.setChecked(paused)
        self.icon.setToolTip(status_text)

    def show_message(self, title: str, body: str) -> None:
        self.icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 5000)
