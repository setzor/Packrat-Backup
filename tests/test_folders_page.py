import pytest

pytest.importorskip("PyQt6")

from packrat.pages.folders import EXCLUDE_PRESETS, FoldersPage


def _text_patterns(page):
    return [ln.strip() for ln in page._excludes_edit.toPlainText().splitlines() if ln.strip()]


def test_preset_checkbox_adds_patterns_to_text_box(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    page._preset_boxes[0].setChecked(True)
    patterns = _text_patterns(page)
    for pattern in EXCLUDE_PRESETS[0][1]:
        assert pattern in patterns
    _folders, excludes, _ignored = page.save()
    assert excludes == patterns


def test_preset_checkbox_uncheck_removes_patterns_from_text_box(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    page._preset_boxes[0].setChecked(True)
    page._preset_boxes[0].setChecked(False)
    assert _text_patterns(page) == []


def test_preset_toggle_keeps_custom_patterns(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], ["**/*.tmp"], [])
    page._preset_boxes[1].setChecked(True)
    assert "**/*.tmp" in _text_patterns(page)
    assert "~/.local/share/Trash" in _text_patterns(page)
    page._preset_boxes[1].setChecked(False)
    assert _text_patterns(page) == ["**/*.tmp"]


def test_uncheck_only_removes_that_presets_patterns(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    page._preset_boxes[0].setChecked(True)
    page._preset_boxes[1].setChecked(True)
    page._preset_boxes[0].setChecked(False)
    patterns = _text_patterns(page)
    assert "~/.local/share/Trash" in patterns
    assert "~/.cache" not in patterns


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


def test_preset_load_does_not_add_patterns_to_text_box(qapp):
    page = FoldersPage()
    page.load(["/home/me/docs"], [], [])
    assert _text_patterns(page) == []
    assert not any(box.isChecked() for box in page._preset_boxes)
