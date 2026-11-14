"""Recovery when the stored backup password cannot be read (issue: 0.3.4)."""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QMessageBox

from packrat.main import MainWindow
from packrat.passwords import load_password, store_password
from packrat.settings import Settings


def _window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    return MainWindow(settings)


def _teardown(window):
    window.tray.hide()
    window.close()


def test_ensure_password_recovers_via_prompt(qapp, tmp_path, monkeypatch):
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        assert window.backend.has_password() is False

        asked = {}

        def fake_question(*args, **kwargs):
            asked["question"] = True
            return QMessageBox.StandardButton.Yes

        def fake_get_text(*args, **kwargs):
            return "correct-horse-battery", True

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
        from PyQt6.QtWidgets import QInputDialog

        monkeypatch.setattr(QInputDialog, "getText", staticmethod(fake_get_text))

        assert window._ensure_password() is True
        assert asked.get("question") is True
        assert window.backend.has_password() is True
        assert load_password() == "correct-horse-battery"
    finally:
        _teardown(window)


def test_ensure_password_declined_returns_false(qapp, tmp_path, monkeypatch):
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
        )
        assert window._ensure_password() is False
        assert window.backend.has_password() is False
    finally:
        _teardown(window)


def test_ensure_password_uses_existing_store(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    store_password("stored-secret-1")
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        assert window._ensure_password() is True
        assert window.backend.has_password() is True
    finally:
        _teardown(window)
