"""Dialog to browse the contents of a snapshot before restoring."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SnapshotBrowserDialog(QDialog):
    """Shows a file tree of what a snapshot contains, Déjà Dup style."""

    closed = pyqtSignal()
    restore_selected_requested = pyqtSignal(list)  # absolute paths to restore
    refresh_requested = pyqtSignal()  # re-list the snapshot, ignoring the cache

    def __init__(
        self,
        snapshot_id: str,
        snapshot_time: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Snapshot {snapshot_id}")
        self.resize(640, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QLabel(f"Contents of the snapshot from {snapshot_time}")
        header.setStyleSheet("font-weight: 600;")
        root.addWidget(header)

        self._loading_label = QLabel("Loading contents…")
        self._loading_label.setStyleSheet("color: #666; font-style: italic;")
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setFixedHeight(6)
        loading_row = QHBoxLayout()
        loading_row.addWidget(self._loading_label)
        loading_row.addWidget(self._loading_bar, 1)
        root.addLayout(loading_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 420)
        root.addWidget(self._tree, 1)

        select_row = QHBoxLayout()
        self._select_button = QPushButton("Restore Selected…")
        self._select_button.setToolTip(
            "Restore only the ticked files and folders into your chosen destination."
        )
        self._select_button.clicked.connect(self._on_restore_selected)
        self._select_button.setEnabled(False)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setToolTip(
            "List the snapshot contents again from the backup destination, "
            "instead of using the cached listing."
        )
        self._refresh_button.clicked.connect(self.refresh_requested)
        self._refresh_button.setEnabled(False)
        self._selection_hint = QLabel("")
        self._selection_hint.setStyleSheet("color: #666;")
        select_row.addWidget(self._select_button)
        select_row.addWidget(self._refresh_button)
        select_row.addWidget(self._selection_hint, 1)
        root.addLayout(select_row)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d9534f;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(lambda: self.done(QDialog.DialogCode.Rejected))
        root.addWidget(buttons)

        self._loading = False
        self._propagating = False
        self._snapshot_id = snapshot_id
        self._tree.itemChanged.connect(self._on_item_changed)

    def reject(self) -> None:
        self.done(QDialog.DialogCode.Rejected)

    def done(self, result: int) -> None:
        self.closed.emit()
        super().done(result)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._loading_label.setVisible(loading)
        self._loading_bar.setVisible(loading)

    def set_refresh_available(self, available: bool) -> None:
        """Enable the refresh button once contents are being fetched fresh."""
        self._refresh_button.setEnabled(available)

    def set_loading_text(self, text: str) -> None:
        """Update the loading label while contents stream in."""
        self._loading_label.setText(text)

    def set_error(self, message: str) -> None:
        self.set_loading(False)
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._refresh_button.setEnabled(True)

    def set_nodes(self, nodes) -> None:
        self.set_loading(False)
        self._error_label.setVisible(False)
        self._tree.blockSignals(True)
        self._tree.clear()
        dirs: dict = {}
        entries = []
        for node in nodes:
            path = str(node.get("name") or "")
            if not path:
                continue
            parts = path.strip("/").split("/")
            if not parts or not parts[0]:
                continue
            entries.append((node, "/".join(parts), parts[-1]))
        for node, key, name in entries:
            if node.get("type") == "dir" and key not in dirs:
                item = QTreeWidgetItem([name, ""])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                dirs[key] = item
        for node, key, name in entries:
            if node.get("type") == "dir":
                item = dirs[key]
            else:
                item = QTreeWidgetItem([name, _node_size(node)])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, "/" + key)
            parent_key = key.rsplit("/", 1)[0] if "/" in key else ""
            parent_item = dirs.get(parent_key, self._tree.invisibleRootItem())
            parent_item.addChild(item)
        self._tree.blockSignals(False)
        self._tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._update_selection_state()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or self._propagating:
            return
        self._propagating = True
        try:
            self._propagate_check_down(item, item.checkState(0))
            self._propagate_check_up(item)
            self._update_selection_state()
        finally:
            self._propagating = False

    def _propagate_check_down(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._propagate_check_down(child, state)

    def _propagate_check_up(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        if parent is None:
            return
        total = parent.childCount()
        checked = sum(
            1 for i in range(total) if parent.child(i).checkState(0) == Qt.CheckState.Checked
        )
        if checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked == total:
            parent.setCheckState(0, Qt.CheckState.Checked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self._propagate_check_up(parent)

    def _selected_paths(self) -> list:
        paths = []
        root_item = self._tree.invisibleRootItem()
        stack = [root_item.child(i) for i in range(root_item.childCount())]
        while stack:
            item = stack.pop()
            state = item.checkState(0)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if state == Qt.CheckState.Checked and path:
                paths.append(str(path))
                continue
            stack.extend(item.child(i) for i in range(item.childCount()))
        return paths

    def _update_selection_state(self) -> None:
        paths = self._selected_paths()
        self._select_button.setEnabled(bool(paths))
        count = len(paths)
        self._selection_hint.setText(f"{count} item{'s' if count != 1 else ''} selected")

    def _on_restore_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        self.restore_selected_requested.emit(paths)

    def snapshot_id(self) -> str:
        return self._snapshot_id


def _node_size(node: dict) -> str:
    if node.get("type") == "dir":
        return ""
    size = node.get("size")
    if size is None:
        return ""
    return _human_size(int(size))


def _human_size(num: float) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"
