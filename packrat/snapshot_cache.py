"""Cache of the most recently listed snapshot contents (#81).

Listing a large snapshot on a cloud repository requires ``restic ls`` to
download every tree blob, which can take minutes. The parsed node list is
therefore cached to disk (keyed by snapshot id + repository location) so a
repeat browse of the same snapshot is instant.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Optional

from . import paths

CACHE_FORMAT = 1
MAX_CACHE_BYTES = 64 * 1024 * 1024


def _cache_file() -> Path:
    return paths.cache_dir() / "snapshot-contents-cache.json"


def _repo_key(repo_location: str) -> str:
    return os.path.expanduser(str(repo_location))


def id_matches(cached_id: str, live_id: str) -> bool:
    """Compare snapshot ids tolerantly.

    The Restore page browses with restic's ``short_id`` (8 hex chars)
    while ``restic backup`` reports the full 64-char id, so a cache
    entry written by one flow must still be found by the other. Restic
    short ids are always a prefix of the full id.
    """
    if not cached_id or not live_id:
        return False
    return cached_id == live_id or live_id.startswith(cached_id) or cached_id.startswith(live_id)


def _matching_key(snapshots: dict, snapshot_id: str) -> Optional[str]:
    if not snapshot_id:
        return None
    if snapshot_id in snapshots:
        return snapshot_id
    for key in snapshots:
        if id_matches(key, snapshot_id):
            return key
    return None


def load_cached_nodes(repo_location: str, snapshot_id: str) -> Optional[List[dict]]:
    data = _read_cache()
    if data is None:
        return None
    key = _matching_key(data.get("snapshots", {}), snapshot_id)
    if not key:
        return None
    entry = data["snapshots"][key]
    if not entry:
        return None
    if entry.get("repo") != _repo_key(repo_location):
        return None
    nodes = entry.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return None
    return nodes


def save_cached_nodes(repo_location: str, snapshot_id: str, nodes: List[dict]) -> None:
    if not snapshot_id or not nodes:
        return
    data = _read_cache() or {"format": CACHE_FORMAT, "snapshots": {}}
    if data.get("format") != CACHE_FORMAT:
        data = {"format": CACHE_FORMAT, "snapshots": {}}
    snapshots = data.setdefault("snapshots", {})
    key = _matching_key(snapshots, snapshot_id) or snapshot_id
    snapshots[key] = {
        "repo": _repo_key(repo_location),
        "time": time.time(),
        "nodes": nodes,
    }
    _prune_to_budget(snapshots)
    _write_cache(data)


def list_cached_snapshot_ids(repo_location: str) -> List[str]:
    """Snapshot ids cached for this repository location (may be stale)."""
    data = _read_cache()
    if data is None:
        return []
    repo = _repo_key(repo_location)
    return [
        snap_id
        for snap_id, entry in data.get("snapshots", {}).items()
        if isinstance(entry, dict) and entry.get("repo") == repo
    ]


def clear_cached_nodes(snapshot_id: str) -> None:
    data = _read_cache()
    if data is None:
        return
    snapshots = data.setdefault("snapshots", {})
    key = _matching_key(snapshots, snapshot_id)
    if key is not None and snapshots.pop(key, None) is not None:
        _write_cache(data)


def _read_cache() -> Optional[dict]:
    path = _cache_file()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_cache(data: dict) -> None:
    path = _cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _prune_to_budget(snapshots: dict) -> None:
    total = sum(len(json.dumps(entry)) for entry in snapshots.values())
    if total <= MAX_CACHE_BYTES:
        return
    ordered = sorted(snapshots.items(), key=lambda item: item[1].get("time", 0))
    for key, _ in ordered[:-1]:
        if total <= MAX_CACHE_BYTES:
            break
        total -= len(json.dumps(snapshots.pop(key)))
