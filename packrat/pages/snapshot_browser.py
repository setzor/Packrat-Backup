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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SnapshotBrowserDialog(QDialog):
    """Shows a file tree of what a snapshot contains, Déjà Dup style."""

    closed = pyqtSignal()

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

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d9534f;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(lambda: self.done(QDialog.DialogCode.Rejected))
        root.addWidget(buttons)

        self._loading = False

    def reject(self) -> None:
        self.done(QDialog.DialogCode.Rejected)

    def done(self, result: int) -> None:
        self.closed.emit()
        super().done(result)

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._loading_label.setVisible(loading)
        self._loading_bar.setVisible(loading)

    def set_error(self, message: str) -> None:
        self.set_loading(False)
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def set_nodes(self, nodes) -> None:
        self.set_loading(False)
        self._error_label.setVisible(False)
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
                dirs[key] = QTreeWidgetItem([name, ""])
        for node, key, name in entries:
            if node.get("type") == "dir":
                item = dirs[key]
            else:
                item = QTreeWidgetItem([name, _node_size(node)])
            parent_key = key.rsplit("/", 1)[0] if "/" in key else ""
            parent_item = dirs.get(parent_key, self._tree.invisibleRootItem())
            parent_item.addChild(item)
        self._tree.sortItems(0, Qt.SortOrder.AscendingOrder)


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
