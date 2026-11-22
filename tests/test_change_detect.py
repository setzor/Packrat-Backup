import pytest

from packrat.change_detect import ChangeReport, analyze_summary, latest_result, record_result


def _summary(
    files=1000, new=10, changed=10, total_bytes=10**9, bytes_new=10**6, bytes_changed=10**6
):
    return {
        "total_files_processed": files,
        "files_new": new,
        "files_changed": changed,
        "total_bytes_processed": total_bytes,
        "bytes_new": bytes_new,
        "bytes_changed": bytes_changed,
    }


def test_normal_change_is_ok():
    report = analyze_summary(_summary())
    assert report.status == "ok"
    assert report.changed_files_ratio == pytest.approx(2.0)


def test_mass_change_is_suspicious():
    report = analyze_summary(_summary(new=600, changed=100))
    assert report.status == "suspicious"
    assert report.changed_files_ratio == pytest.approx(70.0)
    assert "ransomware" in report.reason


def test_small_backup_is_skipped():
    report = analyze_summary(_summary(files=50))
    assert report.status == "skipped"


def test_threshold_is_configurable():
    report = analyze_summary(_summary(new=100, changed=100), changed_files_threshold=10)
    assert report.status == "suspicious"


def test_empty_summary_is_skipped():
    assert analyze_summary({}).status == "skipped"


def test_first_backup_all_new_files_is_skipped_not_suspicious():
    # Fresh repository (first run, or first run after switching to a new
    # cloud destination): every processed file is new, nothing unmodified,
    # nothing "changed" — there is no baseline to compare against.
    report = analyze_summary(_summary(files=828046, new=828046, changed=0))
    assert report.status == "skipped"
    assert "first backup" in report.reason
    assert report.total_files == 828046


def test_ransomware_style_all_changed_still_suspicious():
    # files_changed == all and files_new == 0: a genuine mass change.
    report = analyze_summary(_summary(files=1000, new=0, changed=1000))
    assert report.status == "suspicious"
    assert report.changed_files_ratio == pytest.approx(100.0)


def test_new_files_with_unmodified_baseline_still_analyzed():
    summary = _summary(files=1000, new=900, changed=0)
    summary["files_unmodified"] = 100
    report = analyze_summary(summary)
    assert report.status == "suspicious"
    assert report.changed_files_ratio == pytest.approx(90.0)


def _job(qapp, monkeypatch, tmp_path):
    from packrat.backend import BackupBackend
    from packrat.jobs import BackupJob
    from packrat.settings import Backend, Settings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    s = Settings()
    s.backend_cfg.backend = Backend.LOCAL
    s.backend_cfg.local_path = str(tmp_path / "backups")
    s.change_detection = True
    backend = BackupBackend(s)
    return BackupJob(s, backend), s


def test_job_first_backup_does_not_alert(qapp, monkeypatch, tmp_path):
    job, settings = _job(qapp, monkeypatch, tmp_path)
    alerts = []
    monkeypatch.setattr("packrat.jobs.notify_error", lambda *a, **k: alerts.append(a))
    job.backend.restic.last_backup_summary = _summary(files=828046, new=828046, changed=0)
    job._analyze_changes()
    assert alerts == []
    assert settings.last_change_status == "skipped"


def test_job_mass_change_alerts(qapp, monkeypatch, tmp_path):
    job, settings = _job(qapp, monkeypatch, tmp_path)
    alerts = []
    monkeypatch.setattr("packrat.jobs.notify_error", lambda *a, **k: alerts.append(a))
    job.backend.restic.last_backup_summary = _summary(files=1000, new=0, changed=1000)
    job._analyze_changes()
    assert len(alerts) == 1
    assert settings.last_change_status == "suspicious"


def test_record_and_latest_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("packrat.change_detect._store_path", lambda: tmp_path / "changes.jsonl")
    record_result(ChangeReport("ok", 2.0, 1.0, 1000, 20), snapshot_id="abc123")
    record_result(ChangeReport("suspicious", 80.0, 60.0, 1000, 800), snapshot_id="def456")
    latest = latest_result()
    assert latest["status"] == "suspicious"
    assert latest["snapshot_id"] == "def456"
    assert latest["changed_files_ratio"] == 80.0


def test_latest_result_empty_store(tmp_path, monkeypatch):
    monkeypatch.setattr("packrat.change_detect._store_path", lambda: tmp_path / "changes.jsonl")
    assert latest_result() is None
