"""Quitting from the tray must not claim the app keeps running.

Quitting (tray menu Quit) unwinds through _handle_close, which used to
hide the window and fire the 'Packrat keeps running in the tray'
notification even though the app was about to exit.
"""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from packrat.main import MainWindow  # noqa: E402
from packrat.settings import Settings  # noqa: E402


def _handle_close_via_event(window):
    from PyQt6.QtGui import QCloseEvent

    event = QCloseEvent()
    window._handle_close(event)
    return event


def test_window_close_hides_to_tray_with_notification(qapp, monkeypatch):
    settings = Settings()
    settings.close_to_tray = True
    window = MainWindow(settings)
    messages = []
    monkeypatch.setattr(window.tray, "show_message", lambda t, b: messages.append(b))
    event = _handle_close_via_event(window)
    assert not event.isAccepted()
    assert not window.isVisible() or window.isHidden()
    assert messages, "close-to-tray should notify once"
    assert "keeps running" in messages[0]


def test_quit_skips_tray_notification(qapp, monkeypatch):
    settings = Settings()
    settings.close_to_tray = True
    window = MainWindow(settings)
    messages = []
    monkeypatch.setattr(window.tray, "show_message", lambda t, b: messages.append(b))
    # Simulate the user declining the "backup running" prompt by having no
    # job running; _quit_app asks QApplication to quit, which sends a close
    # event handled by _handle_close while _quitting is set.
    monkeypatch.setattr(window.job, "is_running", lambda: False)
    quit_calls = []
    monkeypatch.setattr(
        "packrat.main.QApplication.instance",
        lambda: type("A", (), {"quit": staticmethod(lambda: quit_calls.append(True))})(),
    )
    window._on_quit()
    assert quit_calls == [True]
    assert window._quitting is True
    # The app.quit() close event must not hide to tray nor notify.
    event = _handle_close_via_event(window)
    assert event.isAccepted()
    assert messages == []


def test_close_to_tray_disabled_quits_cleanly(qapp, monkeypatch):
    settings = Settings()
    settings.close_to_tray = False
    window = MainWindow(settings)
    messages = []
    monkeypatch.setattr(window.tray, "show_message", lambda t, b: messages.append(b))
    monkeypatch.setattr(window.job, "is_running", lambda: False)
    quit_calls = []
    monkeypatch.setattr(
        "packrat.main.QApplication.instance",
        lambda: type("A", (), {"quit": staticmethod(lambda: quit_calls.append(True))})(),
    )
    event = _handle_close_via_event(window)
    assert event.isAccepted()
    assert quit_calls == [True]
    assert messages == []
