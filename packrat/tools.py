"""External tool discovery for restic and rclone."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ToolInfo:
    name: str
    path: Optional[str]
    version: str


def find_tool(name: str, override: Optional[str] = None) -> ToolInfo:
    """Locate an external binary and, best effort, its version."""
    candidates: list[str] = []
    if override:
        candidates.append(override)
    env_key = f"PACKRAT_{name.upper()}_BINARY"
    env_value = os.environ.get(env_key)
    if env_value:
        candidates.append(env_value)
    found = None
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            found = candidate
            break
    if not found:
        found = shutil.which(name)
    if not found:
        return ToolInfo(name, None, "")
    return ToolInfo(name, found, _probe_version(found))


def _probe_version(path: str) -> str:
    import subprocess

    try:
        result = subprocess.run(
            [path, "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    first_line = (result.stdout or result.stderr).strip().splitlines()
    return first_line[0].strip() if first_line else ""


def restic_path(override: Optional[str] = None) -> Optional[str]:
    return find_tool("restic", override).path


def rclone_path(override: Optional[str] = None) -> Optional[str]:
    return find_tool("rclone", override).path
