"""First-run wizard: folders → destination → password → schedule."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from .passwords import validate_password
from .rclone import RcloneRunner
from .settings import Backend


class _IntroPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome to Packrat Backup")
        layout = QVBoxLayout(self)
        label = QLabel(
            "Packrat keeps your files safe with encrypted, incremental "
            "backups powered by restic. This short wizard sets up what to "
            "back up, where to store it, and how often to run."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        self.setCommitPage(True)


class _FoldersPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("What should Packrat back up?")
        layout = QVBoxLayout(self)
        self.registerField("folders*", self)
        self._paths: list[str] = [os.path.expanduser("~")]
        self._label = QLabel("\n".join(self._paths))
        layout.addWidget(self._label)
        add_button = QPushButton("Add folder…")
        add_button.clicked.connect(self._add_folder)
        layout.addWidget(add_button)

    def _add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose a folder to back up", os.path.expanduser("~")
        )
        if directory and directory not in self._paths:
            self._paths.append(directory)
            self._label.setText("\n".join(self._paths))
            self.completeChanged.emit()

    def isComplete(self) -> bool:
        return bool(self._paths)

    def folders(self) -> list:
        return list(self._paths)


class _DestinationPage(QWizardPage):
    def __init__(self, rclone: RcloneRunner) -> None:
        super().__init__()
        self.setTitle("Where should backups be stored?")
        self.setCommitPage(True)
        layout = QVBoxLayout(self)
        self._rclone = rclone

        self._local_radio = QRadioButton("Local folder")
        self._cloud_radio = QRadioButton("OneDrive / Google Drive (via rclone)")
        self._local_radio.setChecked(True)
        self._local_radio.toggled.connect(self.completeChanged.emit)
        layout.addWidget(self._local_radio)
        layout.addWidget(self._cloud_radio)

        self._local_path = QLineEdit(os.path.expanduser("~/.local/share/packrat/backups"))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_local)
        local_row = QHBoxLayout()
        local_row.addWidget(self._local_path, 1)
        local_row.addWidget(browse)
        layout.addLayout(local_row)

        self._remote_combo = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_remotes)
        remote_row = QHBoxLayout()
        remote_row.addWidget(self._remote_combo, 1)
        remote_row.addWidget(refresh)
        layout.addLayout(remote_row)
        self._remote_sub = QLineEdit("packrat-backups")
        layout.addWidget(QLabel("Folder on the remote:"))
        layout.addWidget(self._remote_sub)
        hint = QLabel(
            "Cloud remotes are created with 'rclone config' in a terminal "
            "(choose OneDrive or Google Drive and follow the prompts)."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        rclone.remotes_listed.connect(self._on_remotes)

    def _browse_local(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose a backup destination", self._local_path.text()
        )
        if directory:
            self._local_path.setText(directory)

    def _refresh_remotes(self) -> None:
        self._remote_combo.clear()
        if not RcloneRunner.available():
            self._remote_combo.addItem("rclone not installed")
            return
        self._rclone.list_remotes()

    def _on_remotes(self, remotes) -> None:
        self._remote_combo.clear()
        if remotes:
            self._remote_combo.addItems(remotes)
        else:
            self._remote_combo.addItem("No remotes configured")

    def isComplete(self) -> bool:
        if self._cloud_radio.isChecked():
            text = self._remote_combo.currentText()
            return bool(text) and "not installed" not in text and "No remotes" not in text
        return bool(self._local_path.text().strip())

    def config(self):
        backend = Backend.LOCAL if self._local_radio.isChecked() else Backend.RCLONE
        remote = "" if backend is Backend.LOCAL else self._remote_combo.currentText()
        return {
            "backend": backend,
            "local_path": self._local_path.text().strip(),
            "rclone_remote": remote,
            "rclone_path": self._remote_sub.text().strip() or "packrat-backups",
        }


class _PasswordPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Choose a backup password")
        self.setCommitPage(True)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Backups are encrypted end to end. This password is required "
            "to restore your files, and it is stored in your system keyring."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._repeat_edit = QLineEdit()
        self._repeat_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.textChanged.connect(self.completeChanged.emit)
        self._repeat_edit.textChanged.connect(self.completeChanged.emit)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self._password_edit)
        layout.addWidget(QLabel("Repeat password:"))
        layout.addWidget(self._repeat_edit)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(self._error_label)

    def isComplete(self) -> bool:
        error = validate_password(self._password_edit.text())
        if error:
            self._error_label.setText("")
            return False
        if self._password_edit.text() != self._repeat_edit.text():
            self._error_label.setText("Passwords do not match.")
            return False
        self._error_label.setText("")
        return True

    def password(self) -> str:
        return self._password_edit.text()


class _SchedulePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("When should Packrat run?")
        layout = QVBoxLayout(self)
        self._daily_radio = QRadioButton("Daily (recommended)")
        self._daily_radio.setChecked(True)
        self._weekly_radio = QRadioButton("Weekly")
        self._manual_radio = QRadioButton("Manually only")
        layout.addWidget(self._daily_radio)
        layout.addWidget(self._weekly_radio)
        layout.addWidget(self._manual_radio)
        layout.addStretch(1)

    def choice(self) -> str:
        if self._daily_radio.isChecked():
            return "daily"
        if self._weekly_radio.isChecked():
            return "weekly"
        return "off"


class FirstRunWizard(QWizard):
    finished_ok = pyqtSignal(dict)

    def __init__(self, rclone: RcloneRunner, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Packrat Backup — First run")
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self._folders_page = _FoldersPage()
        self._destination_page = _DestinationPage(rclone)
        self._password_page = _PasswordPage()
        self._schedule_page = _SchedulePage()
        self.addPage(_IntroPage())
        self.addPage(self._folders_page)
        self.addPage(self._destination_page)
        self.addPage(self._password_page)
        self.addPage(self._schedule_page)
        self.accepted.connect(self._on_accepted)

    def _on_accepted(self) -> None:
        result = {
            "folders": self._folders_page.folders(),
            "backend": self._destination_page.config(),
            "password": self._password_page.password(),
            "schedule": self._schedule_page.choice(),
        }
        self.finished_ok.emit(result)
