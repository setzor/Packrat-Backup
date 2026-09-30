"""Folders page: what to back up and what to ignore."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..widgets import FolderListEditor

EXCLUDE_PRESETS = [
    ("Caches", ["~/.cache", "~/.var/app/*/cache", "~/.thumbnails"]),
    ("Trash", ["~/.local/share/Trash"]),
    ("Virtual machine disks", ["*.vdi", "*.vmdk", "*.qcow2", "*.vhd", "*.vhdx"]),
]


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
        presets_label = QLabel("Quick presets:")
        presets_label.setStyleSheet("color: #666;")
        excludes_layout.addWidget(presets_label)
        presets_row = QHBoxLayout()
        self._preset_boxes = []
        for label, _patterns in EXCLUDE_PRESETS:
            box = QCheckBox(label)
            box.toggled.connect(self._on_changed)
            self._preset_boxes.append(box)
            presets_row.addWidget(box)
        presets_row.addStretch(1)
        excludes_layout.addLayout(presets_row)
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
        patterns = list(exclude_patterns)
        for box, (_label, preset_patterns) in zip(self._preset_boxes, EXCLUDE_PRESETS):
            box.blockSignals(True)
            box.setChecked(all(p in patterns for p in preset_patterns))
            box.blockSignals(False)
        self._excludes_edit.setPlainText("\n".join(patterns))

    def save(self) -> None:
        folders = self._folder_editor.folders()
        ignored = self._ignored_editor.folders()
        excludes = [
            line.strip() for line in self._excludes_edit.toPlainText().splitlines() if line.strip()
        ]
        for box, (_label, preset_patterns) in zip(self._preset_boxes, EXCLUDE_PRESETS):
            if box.isChecked():
                for pattern in preset_patterns:
                    if pattern not in excludes:
                        excludes.append(pattern)
        return folders, excludes, ignored
