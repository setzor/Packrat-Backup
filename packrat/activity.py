"""Persistent backup/restore activity log (JSON lines in the config dir)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .paths import config_dir

log = logging.getLogger(__name__)

MAX_ENTRIES = 500


def log_path() -> Path:
    return config_dir() / "activity.jsonl"


def _trim_log() -> None:
    """Keep the activity log bounded.

    The log is append-only JSON lines; without trimming it grows
    forever. Keep the newest MAX_ENTRIES records (compact rewrite,
    best effort — a failed trim never blocks logging).
    """
    path = log_path()
    if not path.is_file():
        return
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    kept = lines[-MAX_ENTRIES:]
    try:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except OSError as exc:
        log.warning("Could not trim activity log: %s", exc)


def log_run(
    operation: str,
    success: bool,
    message: str,
    started_at: str,
    duration_seconds: Optional[float] = None,
    snapshot_id: Optional[str] = "",
) -> None:
    """Append one run record to the activity log."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "operation": operation,
            "success": bool(success),
            "message": message,
            "started_at": started_at,
            "duration_seconds": round(duration_seconds, 1) if duration_seconds else None,
            "snapshot_id": snapshot_id or None,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        _trim_log()
    except OSError as exc:
        log.warning("Could not write activity log: %s", exc)


def load_runs(limit: int = 100) -> list:
    """Return the most recent runs, newest first."""
    path = log_path()
    if not path.is_file():
        return []
    runs = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        log.warning("Could not read activity log: %s", exc)
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            runs.append(entry)
        if len(runs) >= limit:
            break
    return runs
