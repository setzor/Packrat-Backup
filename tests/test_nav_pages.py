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
def test_nav_rows_map_to_matching_pages(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    window = MainWindow(settings)
    try:
        assert window._stack.count() == len(_NAV) == len(_PAGE_TYPES)
        for row, (_label, _key), page_type in zip(range(len(_NAV)), _NAV, _PAGE_TYPES):
            assert isinstance(window._stack.widget(row), page_type), (
                f"row {row} ({_label}) shows {type(window._stack.widget(row)).__name__}, "
                f"expected {page_type.__name__}"
            )
            assert window._nav.item(row).text() == _label
    finally:
        window.tray.hide()
        window.close()
