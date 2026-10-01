import json

from packrat.activity import load_runs, log_path, log_run


def test_log_run_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    log_run("backup", True, "ok", "2026-09-30T10:00:00", 12.3)
    log_run("restore", False, "boom", "2026-09-30T11:00:00", None)
    lines = log_path().read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["operation"] == "backup"
    assert first["success"] is True
    assert first["duration_seconds"] == 12.3


def test_load_runs_newest_first_and_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for i in range(5):
        log_run("backup", True, f"run {i}", f"2026-09-30T10:0{i}:00", i)
    runs = load_runs()
    assert len(runs) == 5
    assert runs[0]["message"] == "run 4"
    assert load_runs(limit=2) == runs[:2]


def test_load_runs_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent"))
    assert load_runs() == []


def test_prune_runs_are_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    log_run("prune", True, "Cleanup complete", "2026-09-30T10:00:00", 5.0)
    runs = load_runs()
    assert len(runs) == 1
    assert runs[0]["operation"] == "prune"
    assert runs[0]["success"] is True
