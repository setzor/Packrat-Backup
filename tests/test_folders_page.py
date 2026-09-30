import pytest

pytest.importorskip("PyQt6")

from packrat.pages.folders import EXCLUDE_PRESETS, FoldersPage


def test_presets_add_patterns_when_checked(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    for box in page._preset_boxes:
        box.setChecked(True)
    _folders, excludes, _ignored = page.save()
    for _label, patterns in EXCLUDE_PRESETS:
        for pattern in patterns:
            assert pattern in excludes


def test_presets_off_by_default(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    _folders, excludes, _ignored = page.save()
    assert excludes == []


def test_preset_roundtrip_preserves_custom_patterns(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], ["**/*.tmp"], [])
    for box in page._preset_boxes:
        box.setChecked(True)
    _folders, excludes, _ignored = page.save()
    assert "**/*.tmp" in excludes
    page.load(["/home/me/docs"], excludes, [])
    assert all(box.isChecked() for box in page._preset_boxes)
    _folders, excludes2, _ignored = page.save()
    assert excludes2 == excludes
    assert len(excludes2) == len(set(excludes2))
