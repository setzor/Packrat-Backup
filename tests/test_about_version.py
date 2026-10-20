"""The About page version must always match the packaged version.

0.3.2 and 0.3.3 shipped with the About page still claiming 0.3.0
because packrat/__init__.py hardcoded a version that release PRs
never touched. __version__ is now derived from the installed
package metadata, which release PRs do bump via pyproject.toml.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from packrat import __version__  # noqa: E402
from packrat.pages.about import AboutPage  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent


def test_about_page_shows_the_package_version(qapp):
    page = AboutPage()
    browsers = page.findChildren(type(page._info))
    assert browsers, "About page should expose its info text browser"
    text = browsers[0].toHtml()
    assert __version__ in text, (
        f"About page shows a version that is not the installed one ({__version__})"
    )


def test_version_matches_pyproject_when_installed():
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match, "pyproject.toml must declare a version"
    if __version__ == "0.0.0+dev":
        pytest.skip("packrat not installed; dev marker in use")
    assert __version__ == match.group(1)
