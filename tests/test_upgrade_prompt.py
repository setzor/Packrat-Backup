"""Stale tray process detection after a package upgrade (#104)."""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QMessageBox

import packrat.main
from packrat.main import MainWindow
from packrat.settings import Settings


def _window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    return MainWindow(settings)


def test_warns_when_installed_version_differs(qapp, tmp_path, monkeypatch):
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        window._started_version = "0.3.3"
        monkeypatch.setattr(packrat.main, "_version_from_metadata", lambda: "0.3.4")
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
        )
        window._warn_if_upgraded()
        assert window._upgrade_prompted is True
    finally:
        window.tray.hide()
        window.close()


def test_no_warning_when_versions_match(qapp, tmp_path, monkeypatch):
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        window._started_version = "0.3.4"
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *a, **k: pytest.fail("prompt shown for matching versions")),
        )
        monkeypatch.setattr(packrat.main, "_version_from_metadata", lambda: "0.3.4")
        window._warn_if_upgraded()
        assert window._upgrade_prompted is False
    finally:
        window.tray.hide()
        window.close()


def test_prompts_only_once(qapp, tmp_path, monkeypatch):
    window = _window(qapp, tmp_path, monkeypatch)
    try:
        window._started_version = "0.3.3"
        monkeypatch.setattr(packrat.main, "_version_from_metadata", lambda: "0.3.4")
        calls = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *a, **k: calls.append(1) or QMessageBox.StandardButton.No),
        )
        window._warn_if_upgraded()
        window._warn_if_upgraded()
        assert len(calls) == 1
    finally:
        window.tray.hide()
        window.close()
