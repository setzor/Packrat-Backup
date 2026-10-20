"""Schedule page must not lock the main window's minimum size (#0.3.2 regression).

The hourly/custom-interval and guards additions in 0.3.2 made the page
taller than the 900x640 design window, so the window could not be
resized smaller. The page content is now scrollable instead.
"""

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QScrollArea  # noqa: E402

from packrat.pages.schedule import SchedulePage  # noqa: E402


def test_schedule_page_minimum_size_stays_compact(qapp):
    page = SchedulePage()
    hint = page.minimumSizeHint()
    assert hint.width() <= 700, f"Schedule page minimum width regressed: {hint.width()}"
    assert hint.height() <= 640, f"Schedule page minimum height regressed: {hint.height()}"


def test_schedule_page_is_scrollable(qapp):
    page = SchedulePage()
    scrolls = page.findChildren(QScrollArea)
    assert scrolls, "Schedule page should wrap its content in a scroll area"
    scroll = scrolls[0]
    assert scroll.widgetResizable()
    content = scroll.widget()
    assert content.minimumSizeHint().height() > 0


def test_schedule_page_content_larger_than_view(qapp):
    # The scroll area's own minimum stays small even when the content is tall.
    page = SchedulePage()
    scroll = page.findChildren(QScrollArea)[0]
    assert scroll.minimumSizeHint().height() <= 200


def test_schedule_page_still_roundtrips(qapp):
    from packrat.settings import ScheduleConfig, ScheduleMode

    cfg = ScheduleConfig(mode=ScheduleMode.INTERVAL, interval_hours=6)
    page = SchedulePage()
    page.load(cfg)
    data = page.save()
    assert data["mode"] is ScheduleMode.INTERVAL
    assert data["interval_hours"] == 6
