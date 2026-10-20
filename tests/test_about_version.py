"""The About page version must always match the installed version.

History of this bug:
- 0.3.2/0.3.3 shipped showing 0.3.0: packrat/__init__.py hardcoded a
  version that release PRs never touched.
- 0.3.4 fixed that with importlib.metadata.version("packrat") - which
  on the maintainer's machine resolved to a stale pip-installed 0.1.1
  shadowing the freshly installed dist-packages metadata.
Now the version is resolved from the metadata physically adjacent to
the running packrat package, immune to shadow installs.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import packrat  # noqa: E402
from packrat import __version__  # noqa: E402
from packrat.pages.about import AboutPage  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent


def test_about_page_shows_the_package_version(qapp):
    page = AboutPage()
    browsers = page.findChildren(type(page._info))
    assert browsers, "About page should expose its info text browser"
    text = browsers[0].toHtml()
    assert __version__ in text, (
        f"About page shows a version that is not the resolved one ({__version__})"
    )


def test_version_matches_pyproject_when_installed():
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match, "pyproject.toml must declare a version"
    if __version__ == "0.0.0+dev":
        pytest.skip("packrat not installed; dev marker in use")
    assert __version__ == match.group(1)


def test_version_resolver_prefers_adjacent_metadata(monkeypatch, tmp_path):
    # Simulate an installed layout: packrat/ next to packrat-X.dist-info
    pkg_dir = tmp_path / "packrat"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "packrat-0.9.9.dist-info").mkdir()
    monkeypatch.setattr(packrat, "__file__", str(pkg_dir / "__init__.py"))
    assert packrat._version_from_metadata() == "0.9.9"


def test_version_resolver_ignores_stale_shadow_install(monkeypatch, tmp_path):
    # A stale packrat elsewhere on sys.path makes importlib.metadata lie;
    # the adjacent resolver must still report the real installed version.
    pkg_dir = tmp_path / "packrat"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "packrat-0.3.4.dist-info").mkdir()
    monkeypatch.setattr(packrat, "__file__", str(pkg_dir / "__init__.py"))
    monkeypatch.setattr(packrat, "_pkg_version", lambda name: "0.1.1", raising=False)
    assert packrat._version_from_metadata() == "0.3.4"


def test_version_resolver_skips_non_version_dirs(monkeypatch, tmp_path):
    pkg_dir = tmp_path / "packrat"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "packrat-tools.dist-info").mkdir()
    (tmp_path / "packrat-x.dist-info").mkdir()
    monkeypatch.setattr(packrat, "__file__", str(pkg_dir / "__init__.py"))
    # No valid adjacent dist-info and importlib finds nothing: raise,
    # which callers translate to the dev marker.
    from importlib.metadata import PackageNotFoundError

    with pytest.raises(PackageNotFoundError):
        packrat._version_from_metadata()
