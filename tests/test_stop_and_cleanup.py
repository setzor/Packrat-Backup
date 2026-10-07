from packrat.restic import ResticRunner, _parse_prune_stats, _parse_size


def test_parse_prune_stats_totals(qapp):
    stderr = """loading indexes...
loading all snapshots...
finding data that is still in use for 3 snapshots
searching used packs...
collecting packs for deletion and repacking
to repack: 537 blobs / 156.912 MiB
this removes: 815 blobs / 59.134 MiB
to delete: 12 blobs / 0 B
total prune: 827 blobs / 59.134 MiB
remaining: 10299 blobs / 676.441 GiB
unused size after prune: 0 B (0.00% of remaining size)
repacking packs
"""
    stats = _parse_prune_stats(stderr)
    assert stats["blobs"] == 827
    assert stats["bytes"] == int(59.134 * 1024 * 1024)


def test_parse_prune_stats_missing_block(qapp):
    assert _parse_prune_stats("some other error output") == {"blobs": 0, "bytes": 0}


def test_parse_size_units():
    assert _parse_size("100", "B") == 100
    assert _parse_size("2", "KiB") == 2048
    assert _parse_size("1.5", "GiB") == int(1.5 * 1024**3)
    assert _parse_size("3", "MiB") == 3 * 1024**2


def test_stop_button_states(qapp):
    from packrat.pages.overview import OverviewPage

    page = OverviewPage()
    assert page._backup_button.text() == "Back Up Now"
    page.set_backup_running(True)
    assert page._backup_button.text() == "Stop Backup"
    assert page._backup_button.isEnabled()
    page.set_backup_running(False)
    assert page._backup_button.text() == "Back Up Now"
    assert page._backup_button.isEnabled()


def test_backup_button_click_routes_to_stop_when_running(qapp):
    from packrat.pages.overview import OverviewPage

    page = OverviewPage()
    requested = []
    page.backup_requested.connect(lambda: requested.append("backup"))
    page.stop_requested.connect(lambda: requested.append("stop"))
    page.set_backup_running(True)
    page._backup_button.click()
    assert requested == ["stop"]
    page.set_backup_running(False)
    page._backup_button.click()
    assert requested == ["stop", "backup"]


def test_set_backup_enabled_ignored_while_running(qapp):
    from packrat.pages.overview import OverviewPage

    page = OverviewPage()
    page.set_backup_running(True)
    page.set_backup_enabled(False)
    assert page._backup_button.isEnabled()


def test_runner_stop_terminates_process(qapp):
    from PyQt6.QtCore import QProcess

    runner = ResticRunner()
    runner.stop()

    class FakeProc:
        def state(self):
            return QProcess.ProcessState.Running

        terminated = False

        def terminate(self):
            self.terminated = True

    fake = FakeProc()
    runner._process = fake
    runner.stop()
    assert fake.terminated is True


def test_runner_stop_noop_without_process(qapp):
    runner = ResticRunner()
    runner.stop()
    assert runner._process is None


def test_cleanup_button_result_text(qapp):
    from packrat.pages.restore import RestorePage

    page = RestorePage()
    page.set_cleanup_result(1234, 62 * 1024 * 1024)
    assert "1234 files" in page._cleanup_label.text()
    assert "62.0 MiB" in page._cleanup_label.text()
    page.set_cleanup_result(0, 0)
    assert page._cleanup_label.text() == "Nothing to clean up — the repository is tidy."


def test_cleanup_button_busy_state(qapp):
    from packrat.pages.restore import RestorePage

    page = RestorePage()
    page.set_cleaning_up(True)
    assert page._cleanup_button.text() == "Cleaning up…"
    assert not page._cleanup_button.isEnabled()
    page.set_cleaning_up(False)
    assert page._cleanup_button.text() == "Clean Up Incomplete Backups"
    assert page._cleanup_button.isEnabled()
