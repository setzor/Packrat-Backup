"""Packrat Backup - a friendly, restic-based backup app for KDE Plasma."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path


def _version_from_metadata() -> str:
    """Resolve the version from THIS package's own installed metadata.

    importlib.metadata.version("packrat") can pick up a stale packrat
    installed elsewhere on sys.path (e.g. an old pip install in the
    user site-packages) that shadows the freshly installed dist-info.
    Prefer the metadata that physically ships next to this package.
    """
    here = Path(__file__).resolve().parent
    for base in (here.parent, here):
        # match e.g. packrat-0.3.4.dist-info / packrat-0.3.4egg-info
        for child in sorted(base.glob("packrat-*.dist-info"), reverse=True):
            name = child.name
            if name.startswith("packrat-") and name.endswith(".dist-info"):
                candidate = name[len("packrat-") : -len(".dist-info")]
                if candidate and candidate[0].isdigit():
                    return candidate
        for child in sorted(base.glob("packrat-*.egg-info"), reverse=True):
            name = child.name
            if name.startswith("packrat-") and name.endswith(".egg-info"):
                candidate = name[len("packrat-") : -len(".egg-info")]
                if candidate and candidate[0].isdigit():
                    return candidate
    return _pkg_version("packrat")


try:
    __version__ = _version_from_metadata()
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0+dev"

APP_NAME = "Packrat Backup"
APP_ID = "io.github.setzor.PackratBackup"
