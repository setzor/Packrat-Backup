import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QSystemTrayIcon  # noqa: E402

from packrat.tray import TrayController  # noqa: E402


def _activate(tray, reason):
    tray._on_activated(reason)


def test_single_click_opens_window(qapp):
    tray = TrayController()
    opened = []
    tray.open_requested.connect(lambda: opened.append(True))
    _activate(tray, QSystemTrayIcon.ActivationReason.Trigger)
    assert opened == [True]


def test_double_click_still_opens(qapp):
    tray = TrayController()
    opened = []
    tray.open_requested.connect(lambda: opened.append(True))
    _activate(tray, QSystemTrayIcon.ActivationReason.DoubleClick)
    assert opened == [True]


def test_double_click_gesture_opens_only_once(qapp):
    # X11 often emits Trigger followed by DoubleClick for one gesture.
    tray = TrayController()
    opened = []
    tray.open_requested.connect(lambda: opened.append(True))
    _activate(tray, QSystemTrayIcon.ActivationReason.Trigger)
    _activate(tray, QSystemTrayIcon.ActivationReason.DoubleClick)
    assert opened == [True]


def test_repeated_single_clicks_each_open(qapp):
    tray = TrayController()
    opened = []
    tray.open_requested.connect(lambda: opened.append(True))
    _activate(tray, QSystemTrayIcon.ActivationReason.Trigger)
    tray._last_open = tray._last_open.addMSecs(-1000)
    _activate(tray, QSystemTrayIcon.ActivationReason.Trigger)
    assert opened == [True, True]


def test_middle_click_and_hover_do_not_open(qapp):
    tray = TrayController()
    opened = []
    tray.open_requested.connect(lambda: opened.append(True))
    _activate(tray, QSystemTrayIcon.ActivationReason.MiddleClick)
    _activate(tray, QSystemTrayIcon.ActivationReason.Context)
    assert opened == []
