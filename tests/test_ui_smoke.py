import pytest

pytest.importorskip("PyQt6")

from packrat.main import _NAV, MainWindow
from packrat.pages.about import AboutPage
from packrat.pages.folders import FoldersPage
from packrat.pages.history import HistoryPage
from packrat.pages.overview import OverviewPage
from packrat.pages.preferences import PreferencesPage
from packrat.pages.restore import RestorePage
from packrat.pages.schedule import SchedulePage
from packrat.pages.storage import StoragePage
from packrat.settings import Settings

_PAGE_TYPES = [
    OverviewPage,
    FoldersPage,
    StoragePage,
    SchedulePage,
    RestorePage,
    HistoryPage,
    PreferencesPage,
    AboutPage,
]


@pytest.mark.skipif(
    pytest.importorskip("PyQt6") is None,
    reason="PyQt6 unavailable",
)
def test_main_window_construction(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    window = MainWindow(settings)
    try:
        assert window.windowTitle() == "Packrat Backup"
        assert window._stack.count() == len(_NAV) == len(_PAGE_TYPES)
        for row, (label, _key), page_type in zip(range(len(_NAV)), _NAV, _PAGE_TYPES):
            assert isinstance(window._stack.widget(row), page_type), (
                f"nav row {row} ({label}) shows "
                f"{type(window._stack.widget(row)).__name__}, expected {page_type.__name__}"
            )
            assert window._nav.item(row).text() == label
        window.overview_page.set_state("2026-09-28 12:00", "", "somewhere", False)
        window.overview_page.set_progress(50, "Backing up")
        window.overview_page.clear_progress()
    finally:
        window.tray.hide()
        window.close()


def test_start_check_runs_backend_check(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    window = MainWindow(settings)
    window.backend.set_password("pw")
    called = {}
    monkeypatch.setattr(window.backend, "check", lambda: called.setdefault("run", True))
    monkeypatch.setattr("packrat.main.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("packrat.main.QMessageBox.warning", lambda *a, **k: None)
    try:
        window.start_check()
        assert called.get("run") is True
        assert not window.overview_page._verify_button.isEnabled()
        window.overview_page.set_checking(False)
        assert window.overview_page._verify_button.isEnabled()
        window._on_check_finished(True, "no errors")
        assert window.overview_page._verify_button.isEnabled()
    finally:
        window.tray.hide()
        window.close()
