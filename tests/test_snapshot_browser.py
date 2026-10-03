from packrat.pages.snapshot_browser import SnapshotBrowserDialog
from packrat.restic import _parse_ls_nodes


def _nodes():
    return [
        {"name": "/tmp", "type": "dir"},
        {"name": "/tmp/docs", "type": "dir"},
        {"name": "/tmp/docs/sub", "type": "dir"},
        {"name": "/tmp/docs/a.txt", "type": "file", "size": 10},
        {"name": "/tmp/docs/sub/b.txt", "type": "file", "size": 20},
        {"name": "/tmp/other.txt", "type": "file", "size": 5},
    ]


def test_parse_ls_nodes_prefers_path_field():
    stdout = (
        '{"struct_type":"node","name":"a.txt","path":"/tmp/a.txt","type":"file","size":2}\n'
        '{"struct_type":"node","name":"tmp","path":"/tmp","type":"dir"}\n'
        '{"struct_type":"snapshot","id":"x"}\n'
    )
    nodes = _parse_ls_nodes(stdout)
    assert [n["name"] for n in nodes] == ["tmp/a.txt", "tmp"]
    assert all(n["name"].startswith("tmp") for n in nodes)


def test_parse_ls_nodes_legacy_name_paths():
    stdout = '{"struct_type":"node","name":"/tmp/a.txt","type":"file"}\n'
    nodes = _parse_ls_nodes(stdout)
    assert nodes[0]["name"] == "tmp/a.txt"


def _find(dialog, path_suffix):
    from PyQt6.QtCore import Qt

    root = dialog._tree.invisibleRootItem()
    stack = [root.child(i) for i in range(root.childCount())]
    while stack:
        item = stack.pop()
        stack.extend(item.child(i) for i in range(item.childCount()))
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and str(data).endswith(path_suffix):
            return item
    return None


def _check(dialog, item, state):
    """Programmatic setCheckState with the dialog's propagation handler."""

    dialog._tree.blockSignals(True)
    item.setCheckState(0, state)
    dialog._tree.blockSignals(False)
    dialog._on_item_changed(item, 0)


def test_browser_selection_logic(qapp):
    dialog = SnapshotBrowserDialog("abc1234", "Jan 1 2026")
    dialog.set_nodes(_nodes())

    # nothing selected initially
    assert dialog._selected_paths() == []
    assert not dialog._select_button.isEnabled()

    docs = _find(dialog, "/tmp/docs")
    a = _find(dialog, "/tmp/docs/a.txt")
    sub = _find(dialog, "/tmp/docs/sub")
    assert docs is not None and a is not None and sub is not None

    # check a single file
    from PyQt6.QtCore import Qt

    _check(dialog, a, Qt.CheckState.Checked)
    assert dialog._selected_paths() == ["/tmp/docs/a.txt"]

    # check a directory: children inherit
    _check(dialog, docs, Qt.CheckState.Checked)
    assert sub.checkState(0) == Qt.CheckState.Checked
    assert a.checkState(0) == Qt.CheckState.Checked
    assert sorted(dialog._selected_paths()) == ["/tmp/docs"]

    # uncheck one child: parent becomes partial, child excluded from paths
    _check(dialog, a, Qt.CheckState.Unchecked)
    assert docs.checkState(0) == Qt.CheckState.PartiallyChecked
    assert dialog._selected_paths() == ["/tmp/docs/sub"]

    dialog.deleteLater()
