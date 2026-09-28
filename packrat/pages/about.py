"""About page: mascot, versions of Packrat, restic, rclone and license info."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..tools import find_tool


def _mascot_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "assets", "packrat-mascot.svg")


class AboutPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel("About Packrat Backup")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        mascot_row = QHBoxLayout()
        mascot_row.addStretch(1)
        mascot = QLabel()
        mascot.setPixmap(_pixmap(_mascot_path()))
        mascot_row.addWidget(mascot)
        mascot_row.addStretch(1)
        root.addLayout(mascot_row)

        tagline = QLabel("A little packrat, quietly keeping your files safe.")
        tagline.setStyleSheet("color: #666; font-style: italic;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tagline)

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


def _pixmap(path: str):
    from PyQt6.QtGui import QPixmap

    pixmap = QPixmap(path)
    if pixmap.isNull():
        pixmap = QPixmap(128, 128)
        pixmap.fill()
    scaled = pixmap.scaled(
        128,
        128,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return scaled
