"""Single-instance guard.

When Packrat is already running (typically in the tray, with no window
open) the desktop launcher spawns a second process. Use a QLocalServer
named socket as a process-wide lock: the first process owns it, and any
later start sends an "activate" message to that socket and exits, so the
existing instance shows its window instead.
"""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QByteArray, QDataStream, QIODevice
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from . import APP_ID

log = logging.getLogger(__name__)

ACTIVATE_MESSAGE = "activate"


class SingleInstance:
    """Owns the single-instance lock for this user session.

    Usage in the entry point::

        guard = SingleInstance(on_activate=window.show_and_raise)
        if not guard.acquire():
            guard.notify_running()
            return 0
        app.exec()
        guard.release()
    """

    def __init__(self, on_activate=None, key: str | None = None) -> None:
        self._key = key or default_key()
        self._on_activate = on_activate
        self._server: QLocalServer | None = None

    # ------------------------------------------------------------------ lock
    def acquire(self) -> bool:
        """Try to become the single instance; True if this process owns it."""
        self.release()
        self._server = QLocalServer()
        if self._server.listen(self._key):
            self._server.newConnection.connect(self._on_new_connection)
            return True
        # A crashed run can leave its socket file behind; clear it and retry.
        QLocalServer.removeServer(self._key)
        if self._server.listen(self._key):
            self._server.newConnection.connect(self._on_new_connection)
            return True
        self.release()
        return False

    def notify_running(self) -> bool:
        """Ask the existing instance to show its window. True if it answered."""
        client = QLocalSocket()
        client.connectToServer(self._key)
        if not client.waitForConnected(2000):
            log.warning("Another Packrat process holds the lock but did not respond")
            client.abort()
            return False
        block = QByteArray()
        stream = QDataStream(block, QIODevice.OpenModeFlag.WriteOnly)
        stream.writeQString(ACTIVATE_MESSAGE)
        client.write(block)
        client.flush()
        client.waitForBytesWritten(2000)
        client.disconnectFromServer()
        return True

    def release(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            server.deleteLater()

    # ------------------------------------------------------------------ server
    def _on_new_connection(self) -> None:
        server = self._server
        if server is None:
            return
        client = server.nextPendingConnection()
        if client is None:
            return
        if not client.waitForReadyRead(1000):
            client.abort()
            return
        stream = QDataStream(client.readAll())
        message = stream.readQString()
        client.disconnectFromServer()
        if message == ACTIVATE_MESSAGE and self._on_activate is not None:
            self._on_activate()


def default_key() -> str:
    """Server key, unique per user so concurrent sessions do not collide."""
    uid = os.getuid() if hasattr(os, "getuid") else "shared"
    return f"{APP_ID}-{uid}"
