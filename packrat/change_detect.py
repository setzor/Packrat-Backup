"""Mass-change detection between consecutive backups (issue #29).

Computes how much of the backed-up data changed in the latest run and
flags anomaly patterns typical of ransomware encryption, accidental
mass deletion, or disk corruption, so Packrat can alert loudly instead
of blindly backing up the damage.

The ratios come from the ``restic backup --json`` summary message, so
stage one needs no extra ``restic diff`` call. Results are appended to
the activity log so the History page records them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .activity import log_path

log = logging.getLogger(__name__)

DEFAULT_CHANGED_FILES_THRESHOLD = 35.0
DEFAULT_CHANGED_DATA_THRESHOLD = 25.0

# Ignore small data sets entirely: ratios are meaningless there and
# false positives would erode trust in the warning.
MIN_FILES_FOR_ANALYSIS = 200
MIN_DATA_FOR_ANALYSIS = 50 * 1024 * 1024  # 50 MiB


@dataclass
class ChangeReport:
    """Outcome of the change-pattern analysis for one backup run."""

    status: str  # "ok" | "suspicious" | "skipped"
    changed_files_ratio: float = 0.0
    changed_data_ratio: float = 0.0
    total_files: int = 0
    changed_files: int = 0
    reason: str = ""


def analyze_summary(
    summary: dict,
    changed_files_threshold: float = DEFAULT_CHANGED_FILES_THRESHOLD,
    changed_data_threshold: float = DEFAULT_CHANGED_DATA_THRESHOLD,
) -> ChangeReport:
    """Judge a backup summary for anomalous change patterns.

    ``summary`` is the parsed final ``summary`` message of a successful
    ``restic backup --json`` run. New-only runs (no baseline snapshot)
    are skipped because ratios against nothing are meaningless.
    """
    total_files = int(summary.get("total_files_processed", 0) or 0)
    if total_files < MIN_FILES_FOR_ANALYSIS:
        return ChangeReport("skipped", total_files=total_files, reason="not enough files")
    total_bytes = int(summary.get("total_bytes_processed", 0) or 0)
    if total_bytes < MIN_DATA_FOR_ANALYSIS:
        return ChangeReport("skipped", total_files=total_files, reason="not enough data")

    files_new = int(summary.get("files_new", 0) or 0)
    files_changed = int(summary.get("files_changed", 0) or 0)
    changed_files = files_new + files_changed
    changed_files_ratio = (changed_files / total_files) * 100.0

    bytes_new = int(summary.get("bytes_new", 0) or 0)
    bytes_changed = int(summary.get("bytes_changed", 0) or 0)
    changed_bytes = bytes_new + bytes_changed
    changed_data_ratio = (changed_bytes / total_bytes) * 100.0 if total_bytes else 0.0

    flagged = changed_files_ratio > changed_files_threshold
    reason = ""
    if flagged:
        reason = (
            f"{changed_files_ratio:.0f}% of {total_files} files changed in one run "
            f"({changed_data_ratio:.0f}% of data). This could be ransomware "
            "encryption or an accidental mass edit."
        )
    return ChangeReport(
        "suspicious" if flagged else "ok",
        changed_files_ratio=changed_files_ratio,
        changed_data_ratio=changed_data_ratio,
        total_files=total_files,
        changed_files=changed_files,
        reason=reason,
    )


def _store_path():
    return log_path().parent / "change_history.jsonl"


def record_result(report: ChangeReport, snapshot_id: str = "") -> None:
    """Persist one analysis result as a JSON line, newest last."""
    import json

    try:
        path = _store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "snapshot_id": snapshot_id or None,
            "status": report.status,
            "changed_files_ratio": round(report.changed_files_ratio, 2),
            "changed_data_ratio": round(report.changed_data_ratio, 2),
            "total_files": report.total_files,
            "changed_files": report.changed_files,
            "reason": report.reason,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        log.warning("Could not write change history: %s", exc)


def latest_result() -> Optional[dict]:
    """Return the most recent stored analysis result, or None."""
    import json

    path = _store_path()
    if not path.is_file():
        return None
    last = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        log.warning("Could not read change history: %s", exc)
        return None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            last = entry
    return last
