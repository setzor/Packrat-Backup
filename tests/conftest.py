import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP_HOME = Path(os.environ.get("PACKRAT_TEST_TMP", "/tmp/packrat-test-home"))
os.environ["XDG_CONFIG_HOME"] = str(_TMP_HOME / "config")
os.environ["XDG_CACHE_HOME"] = str(_TMP_HOME / "cache")
(_TMP_HOME / "config").mkdir(parents=True, exist_ok=True)
(_TMP_HOME / "cache").mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _settings_ini():
    return _TMP_HOME / "config" / "Packrat" / "Packrat Backup.conf"


@pytest.fixture(autouse=True)
def isolated_settings():
    ini = _settings_ini()
    if ini.exists():
        ini.unlink()
    yield
    if ini.exists():
        ini.unlink()
