from PyQt6.QtWidgets import QListWidgetItem

from packrat.rclone import RcloneRunner
from packrat.wizard import _DestinationPage, _FoldersPage


def test_folders_page_add_and_remove(qapp):
    page = _FoldersPage()
    page._list.clear()
    QListWidgetItem("/tmp/docs", page._list)
    QListWidgetItem("/tmp/pics", page._list)
    assert page.folders() == ["/tmp/docs", "/tmp/pics"]
    assert page.isComplete() is True

    page._list.item(0).setSelected(True)
    assert page._remove_button.isEnabled() is True
    page._remove_selected()
    assert page.folders() == ["/tmp/pics"]


def test_folders_page_empty_disables_next(qapp):
    page = _FoldersPage()
    page._list.clear()
    assert page.isComplete() is False


def test_destination_page_shows_guidance_without_remotes(qapp):
    page = _DestinationPage(RcloneRunner())
    page._cloud_radio.setChecked(True)
    page._refresh_remotes()

    loop_timer_wait(qapp)
    help_text = page._help_label.text()
    assert help_text.startswith("No cloud remotes")
    assert "Set up cloud storage" in help_text
    assert page.isComplete() is False


def test_destination_page_accepts_existing_remote(qapp):
    page = _DestinationPage(RcloneRunner())
    page._cloud_radio.setChecked(True)
    page._on_remotes(["my-onedrive"])
    assert page._remote_combo.currentText() == "my-onedrive"
    assert page.isComplete() is True
    cfg = page.config()
    assert cfg["rclone_remote"] == "my-onedrive"


def loop_timer_wait(qapp, ms=1500):
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
