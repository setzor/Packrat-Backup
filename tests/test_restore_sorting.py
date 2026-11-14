"""Restore page snapshot table: resizable columns and sorting (#99)."""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView

from packrat.pages.restore import RestorePage


def _snap(when: str, size: int, short_id: str) -> dict:
    return {
        "time": when,
        "short_id": short_id,
        "paths": ["/home/user/docs"],
        "summary": {"total_bytes_processed": size},
    }


def test_columns_are_user_resizable(qapp):
    page = RestorePage()
    header = page._table.horizontalHeader()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive


def test_size_column_sorts_numerically(qapp):
    page = RestorePage()
    page.set_snapshots(
        [
            _snap("2026-10-01T10:00:00", 2_000_000_000, "aaaa1111"),
            _snap("2026-10-02T10:00:00", 900_000_000, "bbbb2222"),
            _snap("2026-10-03T10:00:00", 5_000_000_000, "cccc3333"),
        ]
    )
    page._table.sortItems(2, Qt.SortOrder.AscendingOrder)
    assert page._table.item(0, 3).text() == "bbbb2222"
    assert page._table.item(1, 3).text() == "aaaa1111"
    assert page._table.item(2, 3).text() == "cccc3333"
    page._table.sortItems(2, Qt.SortOrder.DescendingOrder)
    assert page._table.item(0, 3).text() == "cccc3333"


def test_when_column_sorts_chronologically(qapp):
    page = RestorePage()
    page.set_snapshots(
        [
            _snap("2026-10-03T10:00:00", 1, "cccc3333"),
            _snap("2026-10-01T10:00:00", 1, "aaaa1111"),
        ]
    )
    page._table.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert page._table.item(0, 3).text() == "aaaa1111"


def test_sorting_enabled_after_population(qapp):
    page = RestorePage()
    assert page._table.isSortingEnabled() is False
    page.set_snapshots([_snap("2026-10-01T10:00:00", 1, "aaaa1111")])
    assert page._table.isSortingEnabled() is True
