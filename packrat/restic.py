"""Async wrapper around the restic backup program.

Runs restic in a :class:`QProcess` so the UI stays responsive, emitting
progress messages parsed from restic's ``--json`` status output. The
repository password is handed to restic via the ``RESTIC_PASSWORD``
environment variable of the child process, never via argv or a temp file.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from .tools import restic_path

log = logging.getLogger(__name__)


class ResticProcessError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 0, stderr: str = "") -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class ResticRunner(QObject):
    """Thin async wrapper over the restic CLI."""

    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int, str)  # percent, status text
    snapshots_listed = pyqtSignal(list)  # parsed restic snapshots
    files_listed = pyqtSignal(list)  # parsed restic ls nodes
    dry_run_ready = pyqtSignal(dict)  # parsed restic backup --dry-run summary

    prune_stats_ready = pyqtSignal(dict)  # parsed restic prune stats

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._operation = ""
        self._buffer = ""
        self._stderr_text = ""
        self._last_percent: Optional[int] = None
        self._stopping = False
        self._speed_time: Optional[float] = None
        self._speed_done: int = 0
        self._speed_bytes_per_sec: float = 0.0
        self._last_total_bytes: int = 0
        self._last_bytes_done: int = 0
        self._tick_timer: Optional[QTimer] = None
        self._repo_is_cloud: bool = False
        self.last_snapshot_id: str = ""
        self.last_backup_summary: dict = {}
        self.unreadable_files: List[str] = []
        self._ls_nodes_seen: int = 0

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def available() -> bool:
        return restic_path() is not None

    @staticmethod
    def binary() -> Optional[str]:
        return restic_path()

    def is_running(self) -> bool:
        return (
            self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def _launch(
        self,
        repo: str,
        password: str,
        args: List[str],
        operation: str,
        working_dir: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> None:
        if self.is_running():
            raise ResticProcessError("A restic operation is already running")
        binary = restic_path()
        if not binary:
            raise ResticProcessError("restic binary not found on this system")
        proc = QProcess(self)
        proc.setProgram(binary)
        proc.setArguments(["--repo", repo] + _extended_options(repo, options) + args)
        env = QProcessEnvironment.systemEnvironment()
        if repo.startswith("rclone:"):
            pack_size = (options or {}).get("pack_size")
            if pack_size:
                env.insert("RESTIC_PACK_SIZE", str(pack_size))
        if password:
            env.insert("RESTIC_PASSWORD", password)
        else:
            env.remove("RESTIC_PASSWORD")
        proc.setProcessEnvironment(env)
        if working_dir:
            proc.setWorkingDirectory(working_dir)
        proc.readyReadStandardOutput.connect(lambda: self._on_stdout(proc))
        proc.readyReadStandardError.connect(lambda: self._on_stderr(proc))
        proc.finished.connect(self._on_finished)
        self._process = proc
        self._operation = operation
        self._repo_is_cloud = repo.startswith("rclone:")
        self._buffer = ""
        self._stderr_text = ""
        self._last_percent: Optional[int] = None
        self._stopping = False
        self._speed_time = None
        self._speed_done = 0
        self._speed_bytes_per_sec = 0.0
        self._last_total_bytes = 0
        self._last_bytes_done = 0
        self._ls_nodes_seen = 0
        self._start_tick_timer()
        self.last_backup_summary = {}
        self.unreadable_files = []
        self.last_snapshot_id = ""
        proc.start()

    def _start_tick_timer(self) -> None:
        if self._tick_timer is None:
            self._tick_timer = QTimer(self)
            self._tick_timer.setInterval(3000)
            self._tick_timer.timeout.connect(self._tick_stale_speed)
        self._tick_timer.start()

    def stop(self) -> None:
        """Terminate the running restic operation (and its rclone child)."""
        proc = self._process
        if proc is None or proc.state() == QProcess.ProcessState.NotRunning:
            return
        self._stopping = True
        proc.terminate()

    # ------------------------------------------------------------------ operations
    def init(self, repo: str, password: str, options: Optional[dict] = None) -> None:
        self._launch(
            repo,
            password,
            ["init", "--repository-version", "2"],
            "init",
            options=options,
        )

    def backup(
        self,
        repo: str,
        password: str,
        folders: List[str],
        excludes: List[str],
        dry_run: bool = False,
        options: Optional[dict] = None,
    ) -> None:
        args = ["backup", "--json"]
        if dry_run:
            args.append("--dry-run")
        for pattern in excludes:
            args += ["--exclude", os.path.expanduser(pattern)]
        for folder in folders:
            args.append(os.path.expanduser(folder))
        self._launch(repo, password, args, "dry-run" if dry_run else "backup", options=options)

    def snapshots(self, repo: str, password: str, options: Optional[dict] = None) -> None:
        self._launch(repo, password, ["snapshots", "--json"], "snapshots", options=options)

    def restore(
        self,
        repo: str,
        password: str,
        snapshot_id: str,
        target: str,
        includes: Optional[List[str]] = None,
        options: Optional[dict] = None,
    ) -> None:
        args = ["restore", snapshot_id, "--target", target]
        for pattern in includes or []:
            args += ["--include", pattern]
        self._launch(repo, password, args, "restore", options=options)

    def list_files(
        self, repo: str, password: str, snapshot_id: str, options: Optional[dict] = None
    ) -> None:
        self._launch(repo, password, ["ls", snapshot_id, "--json"], "ls", options=options)

    def prune(
        self, repo: str, password: str, keep_args: List[str], options: Optional[dict] = None
    ) -> None:
        self._launch(
            repo,
            password,
            ["forget", "--prune"] + keep_args,
            "prune",
            options=options,
        )

    def prune_orphans(self, repo: str, password: str, options: Optional[dict] = None) -> None:
        """Run a raw prune to delete unreferenced packs.

        ``forget --prune`` skips orphaned data when no snapshots exist;
        only ``restic prune`` deletes "unreferenced packs".
        """
        self._launch(
            repo,
            password,
            ["prune"],
            "prune",
            options=options,
        )

    def forget(
        self, repo: str, password: str, keep_args: List[str], options: Optional[dict] = None
    ) -> None:
        self._launch(repo, password, ["forget"] + keep_args, "forget", options=options)

    def _check_args(self, read_data: str) -> List[str]:
        args = ["check"]
        if read_data == "full":
            args.append("--read-data")
        elif read_data == "sample":
            args.append("--read-data-subset=10%")
        return args

    def check(
        self, repo: str, password: str, read_data: str = "off", options: Optional[dict] = None
    ) -> None:
        """Manual integrity check; read_data off/sample/full re-reads data blobs."""
        self._launch(repo, password, self._check_args(read_data), "check", options=options)

    def verify(
        self, repo: str, password: str, read_data: str = "sample", options: Optional[dict] = None
    ) -> None:
        """Post-backup restorability proof (#28).

        Uses the same restic arguments as check(); only the operation name
        differs, so the result updates the verified-restore state instead of
        the manual repository-check UI.
        """
        self._launch(repo, password, self._check_args(read_data), "verify", options=options)

    # ------------------------------------------------------------------ plumbing
    def _on_stdout(self, proc: QProcess) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buffer += data
        if self._operation in ("backup", "dry-run"):
            for line in _json_lines(self._buffer):
                self._handle_backup_message(line)
        elif self._operation == "ls":
            self._ls_nodes_seen += _count_ls_nodes(data)
            self.progress.emit(-1, f"Reading snapshot contents — {self._ls_nodes_seen:,} items…")

    def _on_stderr(self, proc: QProcess) -> None:
        data = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_text += data
        self._on_stderr_text(data)

    def _on_stderr_text(self, data: str) -> None:
        for line in data.splitlines():
            stripped = _clean_ansi(line).strip()
            if not stripped:
                continue
            if self._last_percent is None:
                self.progress.emit(-1, stripped)
            else:
                self.progress.emit(self._last_percent, stripped)

    def _handle_backup_message(self, msg: Any) -> None:
        if not isinstance(msg, dict):
            return
        kind = msg.get("message_type")
        if kind == "status":
            percent = int(float(msg.get("percent_done") or 0) * 100)
            if self._last_percent is not None:
                percent = max(percent, self._last_percent)
            self._last_percent = percent
            self._last_total_bytes = int(msg.get("total_bytes") or 0)
            self._last_bytes_done = int(msg.get("bytes_done") or 0)
            self.progress.emit(percent, _status_text(msg, self._byte_counter_text(msg)))
        elif kind == "error":
            item = str(msg.get("item") or "")
            reason = ""
            error = msg.get("error")
            if isinstance(error, dict):
                reason = str(error.get("message") or "")
            if not reason:
                reason = str(error or "")
            line = f"{item}: {reason}" if item else reason
            if line and line not in self.unreadable_files:
                self.unreadable_files.append(line)
        elif kind == "summary":
            snapshot_id = msg.get("snapshot_id")
            if snapshot_id:
                self.last_snapshot_id = str(snapshot_id)
            self.last_backup_summary = dict(msg)
            files = msg.get("total_files_processed", 0)
            size = msg.get("data_added", 0)
            self.progress.emit(
                100,
                f"Backed up {files} files ({_human_size(size)} new data).",
            )

    def _byte_counter_text(self, msg: dict) -> str:
        """Human-readable "10 GiB of 200 GiB" processed counter.

        restic's ``bytes_done`` counts bytes processed *locally* (read,
        chunked, deduplicated) — not bytes uploaded. On cloud repositories
        the upload lags far behind and restic never reports its progress,
        so any speed/ETA derived from ``bytes_done`` would be dishonest
        (e.g. "7.8 GiB/s, 9s left" flickering for an hour). Cloud repos
        show only the processed counter; local repos get speed and ETA.
        """
        total = int(msg.get("total_bytes") or 0)
        done = int(msg.get("bytes_done") or 0)
        if total <= 0 or done <= 0:
            return ""
        if done >= total:
            return "all data processed — finishing cloud upload"
        counter = f"{_human_size(done)} of {_human_size(total)} processed"
        if self._repo_is_cloud:
            return counter
        speed = self._update_speed(done)
        if speed >= 1:
            counter += f", {_human_size(speed)}/s, {_eta_text((total - done) / speed)} left"
        return counter

    def _update_speed(self, done: int) -> float:
        """Sliding-window speed that decays when bytes stop advancing.

        restic's ``bytes_done`` advances at local-processing speed (disk
        reads, easily multiple GiB/s) while the actual cloud upload lags
        far behind, and during the final flush restic sends no status
        messages at all. Decay toward zero when ``bytes_done`` stops
        moving so a fast moment isn't frozen on screen as "7.8 GiB/s,
        9s left" for the next hour.
        """
        now = time.monotonic()
        if self._speed_time is None:
            self._speed_time = now
            self._speed_done = done
            return 0.0
        elapsed = now - self._speed_time
        if elapsed < 1.0:
            return self._speed_bytes_per_sec
        rate = (done - self._speed_done) / elapsed
        if rate < 0:
            rate = 0.0
        if self._speed_bytes_per_sec <= 0:
            self._speed_bytes_per_sec = rate
        else:
            self._speed_bytes_per_sec = 0.5 * rate + 0.5 * self._speed_bytes_per_sec
        self._speed_time = now
        self._speed_done = done
        return self._speed_bytes_per_sec

    def _tick_stale_speed(self) -> None:
        """Re-emit progress with decayed speed while restic is silent.

        restic stops sending status messages during the final cloud flush;
        without this the last computed speed/ETA stays on screen for the
        whole silent stretch. Called periodically during backups.
        """
        if not self.is_running():
            return
        if self._operation not in ("backup", "dry-run"):
            return
        if self._last_percent is None:
            return
        total = self._last_total_bytes
        done = self._last_bytes_done
        if total <= 0 or done <= 0 or done >= total:
            return
        speed = self._update_speed(done)
        text = f"{_human_size(done)} of {_human_size(total)} processed"
        if self._repo_is_cloud:
            text += " — uploading to the cloud…"
        elif speed >= 1:
            text += f", {_human_size(speed)}/s, {_eta_text((total - done) / speed)} left"
        else:
            text += " — waiting…"
        self.progress.emit(self._last_percent, text)

    def _on_finished(self, exit_code: int, exit_status) -> None:
        proc = self._process
        self._process = None
        if self._tick_timer is not None:
            self._tick_timer.stop()
        stdout = self._buffer
        stderr = self._stderr_text
        if proc is not None:
            stderr += bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
            proc.deleteLater()
        success = exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        if self._operation == "snapshots" and success:
            self.snapshots_listed.emit(_parse_snapshots(stdout))
        elif self._operation == "ls" and success:
            self.files_listed.emit(_parse_ls_nodes(stdout))
        elif self._operation == "dry-run":
            self.dry_run_ready.emit(_parse_dry_run_summary(stdout))
        elif self._operation == "prune" and success:
            self.prune_stats_ready.emit(
                _parse_prune_stats(stdout + "\n" + stderr + "\n" + self._stderr_text)
            )
        if self._stopping and not success:
            self._stopping = False
            message = "Stopped by user."
            self._buffer = ""
            self._stderr_text = ""
            self.finished.emit(False, message)
            return
        if self._operation == "backup" and not success and self.last_snapshot_id:
            warning = _extract_exit_warning(stderr)
            if warning:
                files = self.last_backup_summary.get("total_files_processed", 0)
                size = self.last_backup_summary.get("data_added", 0)
                message = (
                    f"Backup saved a snapshot of {files} files "
                    f"({_human_size(size)} new data), but {warning}"
                )
                log.warning("Backup finished with warnings: %s", warning)
                self._buffer = ""
                self._stderr_text = ""
                self.finished.emit(True, message)
                return
        if self._operation == "dry-run" and not success and exit_code == 3:
            summary = _parse_dry_run_summary(stdout)
            warning = _extract_exit_warning(stderr)
            if summary and warning:
                self._buffer = ""
                self._stderr_text = ""
                self.finished.emit(
                    True,
                    f"Preview ready, but {warning}",
                )
                return
        message = _result_message(self._operation, success, exit_code, stderr)
        self._buffer = ""
        self._stderr_text = ""
        self.finished.emit(success, message)

    def _on_error(self, proc: QProcess, error) -> None:
        self._process = None
        proc.deleteLater()
        self.finished.emit(False, f"restic process error: {error}")


def _json_lines(buffer: str):
    for line in buffer.splitlines():
        line = line.strip()
        if not line.startswith("{") and not line.startswith("["):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        yield parsed


def _status_text(msg: dict, counter: str = "") -> str:
    activity = msg.get("current_activity") or msg.get("action") or ""
    files = msg.get("files_done", 0)
    total = msg.get("total_files", 0)
    parts = []
    if activity:
        suffix = f" ({files}/{total} files)" if total else ""
        parts.append(f"{activity}{suffix}")
    if counter:
        parts.append(counter)
    if parts:
        return " — ".join(parts)
    return "Working..."


def _eta_text(seconds: float) -> str:
    secs = int(seconds)
    if secs > 2 * 24 * 3600:
        return "over 2 days"
    hours, rem = divmod(secs, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _human_size(num: float) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


def _parse_prune_stats(stderr: str) -> dict:
    """Parse restic prune's stats block (#63).

    restic prune prints (on stderr, non-JSON):

        to delete: 124233 blobs / 155.654 GiB
        total prune: 124527 blobs / 155.676 GiB

    "total prune" counts everything removed from the repository,
    including data left over by interrupted backups.
    """
    import re

    stats: dict = {"blobs": 0, "bytes": 0}
    match = re.search(r"total prune:\s+(\d+) blobs / ([0-9.]+) ([kMGTP]?i?B)", stderr)
    if match:
        stats["blobs"] = int(match.group(1))
        stats["bytes"] = _parse_size(match.group(2), match.group(3))
    return stats


def _parse_size(value: str, unit: str) -> int:
    multipliers = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "KiB": 1024,
        "MB": 1000**2,
        "MiB": 1024**2,
        "GB": 1000**3,
        "GiB": 1024**3,
        "TB": 1000**4,
        "TiB": 1024**4,
        "PB": 1000**5,
        "PiB": 1024**5,
    }
    return int(float(value) * multipliers.get(unit, 1))


def _parse_snapshots(stdout: str) -> List[dict]:
    stripped = stdout.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        for line in stripped.splitlines():
            line = line.strip()
            if not (line.startswith("{") or line.startswith("[")):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and parsed.get("message_type") == "snapshots_list":
                return parsed.get("snapshots", [])
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and parsed.get("message_type") == "snapshots_list":
        return parsed.get("snapshots", [])
    return []


def _parse_dry_run_summary(stdout: str) -> dict:
    """Extract the final summary message from `restic backup --dry-run --json`."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("message_type") == "summary":
            return parsed
    return {}


def _parse_ls_nodes(stdout: str) -> List[dict]:
    """Parse `restic ls --json` nodes, normalising the name to a full path.

    Older restic emits ``name`` as the absolute path; newer versions emit
    ``name`` as the basename plus ``path`` as the absolute path. The ``path``
    field wins when present.
    """
    nodes: List[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not (isinstance(parsed, dict) and parsed.get("struct_type") == "node"):
            continue
        path = parsed.get("path") or parsed.get("name") or ""
        if not path:
            continue
        node = dict(parsed)
        node["name"] = path.lstrip("/")
        nodes.append(node)
    return nodes


def _count_ls_nodes(data: str) -> int:
    """Count ``restic ls --json`` node lines in a stdout chunk."""
    count = 0
    for line in data.splitlines():
        line = line.strip()
        if line.startswith('{"struct_type":"node"'):
            count += 1
    return count


def _extract_exit_warning(stderr: str) -> str:
    """Pull the human-readable reason out of restic's exit_error JSON.

    restic backup exits 3 ("at least one source file could not be read")
    *after saving the snapshot* of everything it did read; the JSON
    message explains what was skipped so it can be surfaced honestly.
    """
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("message_type") == "exit_error":
            return str(parsed.get("message") or "").strip()
    return ""


def _result_message(operation: str, success: bool, exit_code: int, stderr: str) -> str:
    generic = {
        "init": "Repository initialised",
        "backup": "Backup complete",
        "dry-run": "Backup preview complete",
        "verify": "Backup verified restorable",
        "snapshots": "Snapshots listed",
        "ls": "Snapshot contents listed",
        "restore": "Restore complete",
        "prune": "Cleanup complete",
        "check": "Integrity check passed",
    }
    if success:
        return generic.get(operation, "Operation complete")
    detail = _clean_stderr(stderr)
    base = f"{generic.get(operation, 'Operation')} failed (exit {exit_code})"
    return f"{base}: {detail}" if detail else base


def _clean_stderr(stderr: str) -> str:
    lines = [_clean_ansi(line).strip() for line in stderr.splitlines() if line.strip()]
    for keyword in ("wrong password", "password", "does not exist", "unable to open"):
        for line in lines:
            if keyword in line.lower():
                return line
    return lines[-1] if lines else ""


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _clean_ansi(text: str) -> str:
    """Strip ANSI escape sequences rclone/restic write to stderr.

    rclone emits colour codes and progress redraws on stderr; left in, a
    single line can become a huge unbreakable string that stretches the
    window when it lands in the progress label.
    """
    return _ANSI_RE.sub("", text)


_DEFAULT_RCLONE_ARGS = [
    "serve",
    "restic",
    "--stdio",
    "--checkers=16",
    "--fast-list",
    "--transfers={transfers}",
    "--buffer-size=32M",
]


def _extended_options(repo: str, options: Optional[dict]) -> List[str]:
    """Build restic -o/--option flags for the rclone backend (#64).

    restic spawns ``rclone serve restic --stdio`` itself, so tuning has to
    reach rclone via the rclone.args extended option; the remote spec is
    appended by restic. Non-rclone repositories get no extra options.
    """
    opts = options or {}
    if not repo.startswith("rclone:") or not opts:
        return []
    transfers = int(opts.get("transfers", 0) or 0)
    if transfers <= 0:
        return [
            "-o",
            "rclone.timeout=5m",
            "-o",
            f"rclone.connections={int(opts.get('connections', 8) or 8)}",
        ]
    args = _DEFAULT_RCLONE_ARGS
    formatted = [a.format(transfers=transfers) for a in args]
    return [
        "-o",
        "rclone.timeout=5m",
        "-o",
        f"rclone.connections={int(opts.get('connections', 8) or 8)}",
        "-o",
        "rclone.args=" + " ".join(formatted),
    ]


class Restic:
    """Convenience synchronous helpers used by tests and background workers."""

    @staticmethod
    def run(
        args: List[str], timeout: int = 300, password: str = "", options: Optional[dict] = None
    ) -> Tuple[bool, str, str]:
        import subprocess

        binary = restic_path() or "restic"
        env = dict(os.environ)
        flat = [str(a) for a in args]
        repo = ""
        if flat and flat[0] == "--repo" and len(flat) > 1:
            repo = flat[1]
        if repo.startswith("rclone:") and options and options.get("pack_size"):
            env["RESTIC_PACK_SIZE"] = str(options["pack_size"])
        else:
            env.pop("RESTIC_PACK_SIZE", None)
        if password:
            env["RESTIC_PASSWORD"] = password
        else:
            env.pop("RESTIC_PASSWORD", None)
        completed = subprocess.run(
            [binary] + flat[:2] + _extended_options(repo, options) + flat[2:],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        return completed.returncode == 0, completed.stdout, completed.stderr


def keep_args_from_settings(settings) -> List[str]:
    """Build the restic forget --keep-* argument list from settings."""
    args: List[str] = []
    mapping = (
        ("keep_hourly", "--keep-hourly"),
        ("keep_daily", "--keep-daily"),
        ("keep_weekly", "--keep-weekly"),
        ("keep_monthly", "--keep-monthly"),
        ("keep_yearly", "--keep-yearly"),
    )
    for attr, flag in mapping:
        value = int(getattr(settings, attr, 0) or 0)
        if value > 0:
            args += [flag, str(value)]
    within = str(getattr(settings, "keep_within", "") or "").strip()
    if within:
        args += ["--keep-within", within]
    if not args:
        args = ["--keep-within", "1m"]
    return args
