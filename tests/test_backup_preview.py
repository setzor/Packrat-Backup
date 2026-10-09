from packrat.pages.overview import OverviewPage
from packrat.restic import _parse_dry_run_summary


def _summary_stdout():
    return (
        '{"message_type":"status","percent_done":0.5}\n'
        '{"message_type":"summary","files_new":2,"files_changed":1,'
        '"files_unmodified":7,"total_files_processed":10,'
        '"total_bytes_processed":1048576,"data_added":4096,"dry_run":true}\n'
    )


def test_parse_dry_run_summary_extracts_last_summary():
    parsed = _parse_dry_run_summary(_summary_stdout())
    assert parsed["message_type"] == "summary"
    assert parsed["files_new"] == 2
    assert parsed["total_files_processed"] == 10


def test_parse_dry_run_summary_no_summary():
    assert _parse_dry_run_summary('{"message_type":"status"}\n') == {}
    assert _parse_dry_run_summary("") == {}
    assert _parse_dry_run_summary("not json at all\n") == {}


def test_overview_preview_result_messages(qapp):
    page = OverviewPage()

    page.set_preview_result(
        {
            "files_new": 2,
            "files_changed": 1,
            "total_files_processed": 10,
            "total_bytes_processed": 1048576,
            "data_added": 4096,
        }
    )
    text = page._preview_label.text()
    assert "3 of 10 files" in text
    assert "1.0 MiB" in text
    assert page._preview_label.isVisible() or page._preview_label.text()

    page.set_preview_result(
        {
            "files_new": 0,
            "files_changed": 0,
            "total_files_processed": 5,
            "total_bytes_processed": 10,
            "data_added": 0,
        }
    )
    assert "No changes" in page._preview_label.text()

    page.set_preview_result(
        {
            "files_new": 0,
            "files_changed": 0,
            "total_files_processed": 0,
            "total_bytes_processed": 0,
            "data_added": 0,
        }
    )
    assert "Nothing to back up" in page._preview_label.text()

    page.set_preview_result({})
    assert "Could not estimate" in page._preview_label.text()

    page.clear_preview()
    assert page._preview_label.text() == ""


def test_overview_preview_button_states(qapp):
    page = OverviewPage()
    assert page._preview_button.text() == "Estimate Next Backup"
    assert page._preview_button.isEnabled()
    page.set_previewing(True)
    assert page._preview_button.text() == "Estimating…"
    assert not page._preview_button.isEnabled()
    page.set_previewing(False)
    assert page._preview_button.isEnabled()
