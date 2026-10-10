"""Routing tests for snapshot listing results (PRs #85/#86 follow-up).

The in-flight ``restic ls`` result must reach the browser dialog only when
the dialog is for the same snapshot, and must never poison the contents
cache of a different snapshot (e.g. a background pre-cache listing for a
new backup finishing while an older cached dialog stays open).

The MainWindow routing methods are bound to a bare harness because they
only touch ``self._browser``, ``self._ls_snapshot_id`` and
``self.backend`` — no Qt widget state is needed.
"""

from types import MethodType

from packrat import snapshot_cache
from packrat.main import MainWindow
from packrat.pages.snapshot_browser import SnapshotBrowserDialog


class _Harness:
    def __init__(self):
        self._browser = None
        self._ls_snapshot_id = ""
        self.backend = type(
            "Backend", (), {"repo_location": lambda self: "rclone:onedrive:packrat"}
        )()()

    def _on_files_ready(self, nodes):
        return MethodType(MainWindow._on_files_ready, self)(nodes)

    def _on_operation_finished(self, operation, success, message):
        return MethodType(MainWindow._on_operation_finished, self)(operation, success, message)


def _nodes(tag):
    return [
        {"name": f"/{tag}", "type": "dir"},
        {"name": f"/{tag}/file.txt", "type": "file", "size": 3},
    ]


def test_files_ready_routes_to_matching_dialog(qapp):
    window = _Harness()
    dialog = SnapshotBrowserDialog("snapA", "Jan 1 2026")
    window._browser = dialog
    window._ls_snapshot_id = "snapA"
    window._on_files_ready(_nodes("a"))
    assert window._ls_snapshot_id == ""
    assert snapshot_cache.load_cached_nodes("rclone:onedrive:packrat", "snapA") == _nodes("a")


def test_precache_listing_does_not_touch_open_dialog(qapp):
    window = _Harness()
    dialog = SnapshotBrowserDialog("snapA", "Jan 1 2026")
    dialog.set_nodes(_nodes("a"))
    window._browser = dialog
    window._ls_snapshot_id = "snapB"
    window._on_files_ready(_nodes("b"))
    assert window._ls_snapshot_id == ""
    assert snapshot_cache.load_cached_nodes("rclone:onedrive:packrat", "snapB") == _nodes("b")
    assert snapshot_cache.load_cached_nodes("rclone:onedrive:packrat", "snapA") == _nodes("a")
    assert dialog.snapshot_id() == "snapA"


def test_ls_failure_clears_state_without_dialog(qapp):
    window = _Harness()
    window._ls_snapshot_id = "snapB"
    window._on_operation_finished("ls", False, "boom")
    assert window._ls_snapshot_id == ""


def test_ls_failure_reports_only_to_matching_dialog(qapp):
    window = _Harness()
    dialog = SnapshotBrowserDialog("snapA", "Jan 1 2026")
    window._browser = dialog
    window._ls_snapshot_id = "snapB"
    window._on_operation_finished("ls", False, "boom")
    assert window._ls_snapshot_id == ""
    assert not dialog._error_label.isVisibleTo(dialog)
