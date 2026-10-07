import pytest

from packrat.pages.preferences import PreferencesPage
from packrat.settings import Settings, update_autostart


@pytest.fixture
def autostart_dir(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    return config / "autostart"


def test_preferences_page_roundtrip(qapp):
    settings = Settings()
    settings.close_to_tray = False
    settings.run_at_startup = False
    page = PreferencesPage()
    page.load(settings)
    assert page.save() == {
        "close_to_tray": False,
        "run_at_startup": False,
        "restore_refresh_minutes": 60,
        "cloud_connections": 8,
        "cloud_pack_size": 64,
        "verify_after_backup": "sample",
        "change_detection": True,
        "changed_files_threshold": 35,
    }

    page._close_to_tray_check.setChecked(True)
    page._run_at_startup_check.setChecked(True)
    data = page.save()
    assert data == {
        "close_to_tray": True,
        "run_at_startup": True,
        "restore_refresh_minutes": 60,
        "cloud_connections": 8,
        "cloud_pack_size": 64,
        "verify_after_backup": "sample",
        "change_detection": True,
        "changed_files_threshold": 35,
    }


def test_new_settings_defaults(qapp):
    settings = Settings()
    assert settings.close_to_tray is True
    assert settings.run_at_startup is True
    assert settings.restore_refresh_minutes == 60


def test_close_to_tray_persists(qapp):
    settings = Settings()
    settings.close_to_tray = False
    settings.save()
    reloaded = Settings()
    assert reloaded.close_to_tray is False


def test_autostart_install_and_remove(autostart_dir):
    assert update_autostart(True) is True
    entry = autostart_dir / "org.packrat.Backup.desktop"
    assert entry.exists()
    content = entry.read_text()
    assert "Exec=" in content
    assert "--tray" in content

    assert update_autostart(False) is True
    assert not entry.exists()


def test_autostart_remove_when_absent(autostart_dir):
    assert update_autostart(False) is True
    assert not (autostart_dir / "org.packrat.Backup.desktop").exists()


def test_restore_refresh_setting_roundtrip(qapp):
    settings = Settings()
    settings.restore_refresh_minutes = 120
    page = PreferencesPage()
    page.load(settings)
    assert page.save()["restore_refresh_minutes"] == 120
    page._restore_refresh_spin.setValue(0)
    assert page.save()["restore_refresh_minutes"] == 0


def test_preferences_page_minimum_size_stays_compact(qapp):
    """The window cannot shrink below its widest page's minimum (#64 regression).

    A row of widgets accidentally added to a horizontal layout as siblings
    once made this page hundreds of pixels wide, locking the main window's
    minimum width. Keep the page comfortably inside the 900x640 design size.
    """
    page = PreferencesPage()
    hint = page.minimumSizeHint()
    assert hint.width() <= 700, f"Preferences page minimum width regressed: {hint.width()}"
    assert hint.height() <= 900, f"Preferences page minimum height regressed: {hint.height()}"
