"""About page: versions of Packrat, restic, rclone and licensing info."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from .. import __version__
from ..tools import find_tool


class AboutPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel("About Packrat Backup")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        restic = find_tool("restic")
        rclone = find_tool("rclone")
        info = QTextBrowser()
        info.setOpenExternalLinks(True)
        info.setHtml(
            "<p><b>Packrat Backup</b> " + __version__ + "</p>"
            "<p>A friendly, restic-powered backup app for KDE Plasma with "
            "OneDrive and Google Drive support via rclone.</p>"
            "<p>External tools detected:<br>"
            "restic: " + (restic.version or "not found") + "<br>"
            "rclone: " + (rclone.version or "not found") + "</p>"
            "<p>Licensed under the GNU General Public License v3 or later. "
            "Backups are always encrypted with the password stored in your "
            "system keyring (KWallet on Plasma).</p>"
            '<p><a href="https://github.com/setzor/Packrat-Backup">Project page</a></p>'
        )
        root.addWidget(info, 1)
