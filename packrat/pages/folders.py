"""Folders page: what to back up and what to ignore."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..widgets import FolderListEditor


class FoldersPage(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Folders to back up")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        folders_box = QGroupBox("Included folders")
        folders_layout = QVBoxLayout(folders_box)
        self._folder_editor = FolderListEditor()
        self._folder_editor.changed.connect(self._on_changed)
        folders_layout.addWidget(self._folder_editor)
        root.addWidget(folders_box)

        ignored_box = QGroupBox("Ignored folders")
        ignored_layout = QVBoxLayout(ignored_box)
        ignored_hint = QLabel(
            "Folders listed here are never backed up, even if they are "
            "inside an included folder above."
        )
        ignored_hint.setStyleSheet("color: #666;")
        ignored_hint.setWordWrap(True)
        ignored_layout.addWidget(ignored_hint)
        self._ignored_editor = FolderListEditor()
        self._ignored_editor.changed.connect(self._on_changed)
        ignored_layout.addWidget(self._ignored_editor)
        root.addWidget(ignored_box)

        excludes_box = QGroupBox("Ignore patterns (one per line)")
        excludes_layout = QVBoxLayout(excludes_box)
        self._excludes_edit = QTextEdit()
        self._excludes_edit.setPlaceholderText("~/.cache\n~/.local/share/Trash\n**/*.tmp")
        self._excludes_edit.setFixedHeight(120)
        self._excludes_edit.textChanged.connect(self._on_changed)
        excludes_layout.addWidget(self._excludes_edit)
        root.addWidget(excludes_box)
        root.addStretch(1)

    def _on_changed(self) -> None:
        self.changed.emit()

    # ------------------------------------------------------------------ state
    def load(self, folders, exclude_patterns, ignored_folders) -> None:
        self._folder_editor.set_folders(list(folders))
        self._ignored_editor.set_folders(list(ignored_folders))
        self._excludes_edit.setPlainText("\n".join(exclude_patterns))

    def save(self) -> None:
        folders = self._folder_editor.folders()
        ignored = self._ignored_editor.folders()
        excludes = [
            line.strip() for line in self._excludes_edit.toPlainText().splitlines() if line.strip()
        ]
        return folders, excludes, ignored
