import pytest

pytest.importorskip("PyQt6")

from packrat.main import MainWindow
from packrat.settings import Settings


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
        assert window._stack.count() == 7
        window.overview_page.set_state("2026-09-28 12:00", "", "somewhere", False)
        window.overview_page.set_progress(50, "Backing up")
        window.overview_page.clear_progress()
    finally:
        window.tray.hide()
        window.close()
