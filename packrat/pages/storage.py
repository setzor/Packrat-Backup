"""Storage page: local folder or rclone remote (OneDrive/Google Drive)."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..rclone import RcloneRunner
from ..rclone_setup import no_remotes_help, open_rclone_config_ui, rclone_missing_help
from ..settings import Backend


class StoragePage(QWidget):
    changed = pyqtSignal()

    def __init__(
        self,
        rclone: RcloneRunner,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._rclone = rclone
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Where to store your backups")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        location_box = QGroupBox("Storage location")
        location_layout = QVBoxLayout(location_box)
        self._local_radio = QRadioButton("Local folder")
        self._local_radio.toggled.connect(self._on_mode_changed)
        self._remote_radio = QRadioButton("Cloud storage (via rclone)")
        self._remote_radio.toggled.connect(self._on_mode_changed)
        location_layout.addWidget(self._local_radio)
        location_layout.addWidget(self._remote_radio)
        root.addWidget(location_box)

        local_box = QGroupBox("Local backup folder")
        local_layout = QHBoxLayout(local_box)
        self._local_path_edit = QLineEdit()
        self._local_path_edit.textChanged.connect(self._emit_changed)
        self._local_browse_button = QPushButton("Browse…")
        self._local_browse_button.clicked.connect(self._on_browse_local)
        local_layout.addWidget(self._local_path_edit, 1)
        local_layout.addWidget(self._local_browse_button)
        root.addWidget(local_box)

        remote_box = QGroupBox("rclone remote")
        remote_layout = QVBoxLayout(remote_box)
        remote_row = QHBoxLayout()
        self._remote_combo = QComboBox()
        self._refresh_button = QPushButton("Refresh remotes")
        self._refresh_button.clicked.connect(self._on_refresh)
        self._setup_button = QPushButton("Set up cloud storage…")
        self._setup_button.clicked.connect(self._on_setup_clicked)
        remote_row.addWidget(self._remote_combo, 1)
        remote_row.addWidget(self._refresh_button)
        remote_row.addWidget(self._setup_button)
        remote_layout.addLayout(remote_row)
        self._remote_path_edit = QLineEdit()
        self._remote_path_edit.setPlaceholderText("packrat-backups")
        self._remote_path_edit.textChanged.connect(self._emit_changed)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder on the remote:"))
        path_row.addWidget(self._remote_path_edit, 1)
        remote_layout.addLayout(path_row)
        self._help_label = QLabel("")
        self._help_label.setWordWrap(True)
        self._help_label.setStyleSheet("color: #555;")
        remote_layout.addWidget(self._help_label)
        root.addWidget(remote_box)
        root.addStretch(1)

        self._rclone.remotes_listed.connect(self._on_remotes_listed)
        self._loading = False

    # ------------------------------------------------------------------ handlers
    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    def _on_mode_changed(self) -> None:
        local = self._local_radio.isChecked()
        self._local_path_edit.setEnabled(local)
        self._local_browse_button.setEnabled(local)
        self._remote_combo.setEnabled(not local)
        self._remote_path_edit.setEnabled(not local)
        self._refresh_button.setEnabled(not local)
        self._setup_button.setEnabled(not local)
        self._emit_changed()

    def _on_browse_local(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        directory = QFileDialog.getExistingDirectory(
            self, "Choose a folder for backups", os.path.expanduser("~")
        )
        if directory:
            self._local_path_edit.setText(directory)

    def _on_refresh(self) -> None:
        if not RcloneRunner.available():
            self._remote_combo.clear()
            self._remote_combo.addItem("rclone not installed")
            self._help_label.setText(rclone_missing_help())
            return
        self._refresh_button.setEnabled(False)
        self._rclone.list_remotes()

    def _on_setup_clicked(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        opened, message = open_rclone_config_ui()
        QMessageBox.information(self, "Cloud storage setup", message)
        if opened:
            self._on_refresh()

    def _on_remotes_listed(self, remotes) -> None:
        self._refresh_button.setEnabled(True)
        current = self._remote_combo.currentText()
        self._remote_combo.clear()
        for remote in remotes:
            self._remote_combo.addItem(remote)
        if current in remotes:
            self._remote_combo.setCurrentText(current)
        if remotes:
            self._help_label.setText(
                "Found " + str(len(remotes)) + " remote(s). Pick the one to store backups on."
            )
        else:
            self._remote_combo.addItem("No remotes configured")
            self._help_label.setText(no_remotes_help())

    # ------------------------------------------------------------------ state
    def load(self, backend_cfg) -> None:
        self._loading = True
        try:
            is_local = backend_cfg.backend is Backend.LOCAL
            self._local_radio.setChecked(is_local)
            self._remote_radio.setChecked(not is_local)
            self._local_path_edit.setText(backend_cfg.local_path)
            self._remote_path_edit.setText(backend_cfg.rclone_path)
            if backend_cfg.rclone_remote:
                self.set_remote_name(backend_cfg.rclone_remote)
            self._on_mode_changed()
        finally:
            self._loading = False

    def set_remote_name(self, name: str) -> None:
        index = self._remote_combo.findText(name)
        if index >= 0:
            self._remote_combo.setCurrentIndex(index)
        elif name:
            self._remote_combo.addItem(name)
            self._remote_combo.setCurrentText(name)

    def refresh_remotes(self) -> None:
        self._on_refresh()

    def save(self):
        backend = Backend.LOCAL if self._local_radio.isChecked() else Backend.RCLONE
        remote = self._remote_combo.currentText() if backend is Backend.RCLONE else ""
        if remote == "No remotes configured":
            remote = ""
        return {
            "backend": backend,
            "local_path": self._local_path_edit.text().strip(),
            "rclone_remote": remote,
            "rclone_path": self._remote_path_edit.text().strip() or "packrat-backups",
        }
