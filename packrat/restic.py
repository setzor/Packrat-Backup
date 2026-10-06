"""Async wrapper around the restic backup program.

Runs restic in a :class:`QProcess` so the UI stays responsive, emitting
progress messages parsed from restic's ``--json`` status output. The
repository password is handed to restic via the ``RESTIC_PASSWORD``
environment variable of the child process, never via argv or a temp file.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from .tools import restic_path


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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._operation = ""
        self._buffer = ""
        self._last_percent: Optional[int] = None
        self.last_snapshot_id: str = ""
        self.last_backup_summary: dict = {}

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
        self._buffer = ""
        self._last_percent: Optional[int] = None
        self.last_backup_summary = {}
        proc.start()

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

    def _on_stderr(self, proc: QProcess) -> None:
        data = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        self._on_stderr_text(data)

    def _on_stderr_text(self, data: str) -> None:
        for line in data.splitlines():
            stripped = line.strip()
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
            self.progress.emit(percent, _status_text(msg))
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

    def _on_finished(self, exit_code: int, exit_status) -> None:
        proc = self._process
        self._process = None
        stdout = self._buffer
        stderr = ""
        if proc is not None:
            stderr = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
            proc.deleteLater()
        success = exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        if self._operation == "snapshots" and success:
            self.snapshots_listed.emit(_parse_snapshots(stdout))
        elif self._operation == "ls" and success:
            self.files_listed.emit(_parse_ls_nodes(stdout))
        elif self._operation == "dry-run" and success:
            self.dry_run_ready.emit(_parse_dry_run_summary(stdout))
        message = _result_message(self._operation, success, exit_code, stderr)
        self._buffer = ""
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


def _status_text(msg: dict) -> str:
    activity = msg.get("current_activity") or msg.get("action") or ""
    files = msg.get("files_done", 0)
    total = msg.get("total_files", 0)
    if activity:
        suffix = f" ({files}/{total} files)" if total else ""
        return f"{activity}{suffix}"
    return "Working..."


def _human_size(num: float) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


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
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for keyword in ("wrong password", "password", "does not exist", "unable to open"):
        for line in lines:
            if keyword in line.lower():
                return line
    return lines[-1] if lines else ""


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
        return ["-o", f"rclone.connections={int(opts.get('connections', 8) or 8)}"]
    args = _DEFAULT_RCLONE_ARGS
    formatted = [a.format(transfers=transfers) for a in args]
    return [
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
