import json

from packrat import paths, snapshot_cache


def _nodes():
    return [
        {"name": "/tmp", "type": "dir"},
        {"name": "/tmp/docs", "type": "dir"},
        {"name": "/tmp/docs/a.txt", "type": "file", "size": 10},
    ]


def test_roundtrip(tmp_path):
    snapshot_cache.save_cached_nodes("rclone:onedrive:packrat", "abc1234", _nodes())
    loaded = snapshot_cache.load_cached_nodes("rclone:onedrive:packrat", "abc1234")
    assert loaded == _nodes()


def test_repo_mismatch_is_miss(tmp_path):
    snapshot_cache.save_cached_nodes("rclone:onedrive:packrat", "abc1234", _nodes())
    assert snapshot_cache.load_cached_nodes("rclone:gdrive:packrat", "abc1234") is None
    assert snapshot_cache.load_cached_nodes("/other/local/repo", "abc1234") is None


def test_unknown_snapshot_is_miss(tmp_path):
    snapshot_cache.save_cached_nodes("rclone:onedrive:packrat", "abc1234", _nodes())
    assert snapshot_cache.load_cached_nodes("rclone:onedrive:packrat", "other") is None


def test_clear_cached_nodes(tmp_path):
    snapshot_cache.save_cached_nodes("repo", "abc1234", _nodes())
    snapshot_cache.clear_cached_nodes("abc1234")
    assert snapshot_cache.load_cached_nodes("repo", "abc1234") is None


def test_list_cached_snapshot_ids_scoped_to_repo(tmp_path):
    snapshot_cache.save_cached_nodes("repoA", "snap1", _nodes())
    snapshot_cache.save_cached_nodes("repoB", "snap2", _nodes())
    assert snapshot_cache.list_cached_snapshot_ids("repoA") == ["snap1"]
    assert snapshot_cache.list_cached_snapshot_ids("repoB") == ["snap2"]


def test_size_budget_evicts_oldest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot_cache, "MAX_CACHE_BYTES", 1)
    snapshot_cache.save_cached_nodes("repo", "snap1", _nodes())
    snapshot_cache.save_cached_nodes("repo", "snap2", _nodes())
    ids = snapshot_cache.list_cached_snapshot_ids("repo")
    assert ids == ["snap2"]
    assert snapshot_cache.load_cached_nodes("repo", "snap1") is None
    assert snapshot_cache.load_cached_nodes("repo", "snap2") == _nodes()


def test_corrupt_cache_file_is_ignored(tmp_path):
    path = snapshot_cache._cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all")
    assert snapshot_cache.load_cached_nodes("repo", "snap1") is None
    snapshot_cache.save_cached_nodes("repo", "snap1", _nodes())
    assert snapshot_cache.load_cached_nodes("repo", "snap1") == _nodes()


def test_cache_file_lives_in_cache_dir(tmp_path):
    snapshot_cache.save_cached_nodes("repo", "snap1", _nodes())
    path = snapshot_cache._cache_file()
    assert path == paths.cache_dir() / "snapshot-contents-cache.json"
    data = json.loads(path.read_text())
    assert data["snapshots"]["snap1"]["repo"] == "repo"
    assert data["snapshots"]["snap1"]["nodes"] == _nodes()


def test_short_id_finds_full_id_entry(tmp_path):
    full_id = "abcd1234" + "e" * 24
    snapshot_cache.save_cached_nodes("rclone:onedrive:idmatch", full_id, _nodes())
    loaded = snapshot_cache.load_cached_nodes("rclone:onedrive:idmatch", "abcd1234")
    assert loaded == _nodes()


def test_full_id_finds_short_id_entry(tmp_path):
    full_id = "abcd1234" + "e" * 24
    snapshot_cache.save_cached_nodes("rclone:onedrive:idmatch", "abcd1234", _nodes())
    loaded = snapshot_cache.load_cached_nodes("rclone:onedrive:idmatch", full_id)
    assert loaded == _nodes()


def test_save_reuses_matching_entry_instead_of_duplicating(tmp_path):
    snapshot_cache.save_cached_nodes("repo-idmatch", "abcd1234", _nodes())
    snapshot_cache.save_cached_nodes("repo-idmatch", "abcd1234" + "e" * 24, _nodes())
    ids = snapshot_cache.list_cached_snapshot_ids("repo-idmatch")
    assert len(ids) == 1
    assert snapshot_cache.load_cached_nodes("repo-idmatch", "abcd1234" + "e" * 24) is not None
    assert snapshot_cache.load_cached_nodes("repo-idmatch", "abcd1234") is not None


def test_clear_by_short_id_removes_full_id_entry(tmp_path):
    full_id = "abcd1234" + "e" * 24
    snapshot_cache.save_cached_nodes("repo-idmatch", full_id, _nodes())
    snapshot_cache.clear_cached_nodes("abcd1234")
    assert snapshot_cache.load_cached_nodes("repo-idmatch", full_id) is None


def test_unrelated_id_is_not_matched_by_prefix_rule(tmp_path):
    snapshot_cache.save_cached_nodes("repo", "ffff0000", _nodes())
    assert snapshot_cache.load_cached_nodes("repo-idmatch", "abcd1234") is None
