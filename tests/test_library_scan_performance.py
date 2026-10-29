"""Regression tests for library/session list performance (scan pruning, cleanup throttle)."""

import json
import os
import zipfile

from backend.api.routes.adventures import session_assets
from backend.core.config import settings
from backend.engine.adventures import adventure_updates


def _write_adv(path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": "1.2", "adventure": {"title": title}}), encoding="utf-8")


def test_walk_skips_asset_and_session_folders(tmp_path):
    # Arrange
    _write_adv(tmp_path / "top.adv", "Top")
    _write_adv(tmp_path / "samples" / "nested.adv", "Nested")
    _write_adv(tmp_path / "library" / "adv-1" / "hidden.adv", "Library")
    _write_adv(tmp_path / "sessions" / "s-1" / "hidden.adv", "Session")
    _write_adv(tmp_path / "019e5bb4-32ea-7b56-a1e5-2183655d6803" / "hidden.adv", "Uuid")

    # Act
    found = {
        filename
        for root, files in adventure_updates._walk_adventure_dirs(str(tmp_path))
        for filename in files
        if filename.endswith(".adv")
    }
    visited = [root for root, _ in adventure_updates._walk_adventure_dirs(str(tmp_path))]

    # Assert
    assert found == {"top.adv", "nested.adv"}
    assert not any(os.sep + "library" in root or os.sep + "sessions" in root for root in visited)


def test_adz_manifest_is_read_without_loading_other_members(tmp_path):
    # Arrange
    archive = tmp_path / "pack.adz"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("adventure.adv", json.dumps({"adventure": {"title": "Zipped"}}))
        zf.writestr("images/big.bin", b"\0" * 1024)

    # Act
    manifest = adventure_updates._read_manifest(str(archive), ".adz")

    # Assert
    assert manifest == {"adventure": {"title": "Zipped"}}


def test_scan_file_reuses_entry_until_file_changes(tmp_path, monkeypatch):
    # Arrange
    adv = tmp_path / "cached.adv"
    _write_adv(adv, "First")
    monkeypatch.setattr(adventure_updates, "_FILE_CACHE", {})
    calls = []
    original_parse = adventure_updates._parse_file

    def counting_parse(*args):
        calls.append(args)
        return original_parse(*args)

    monkeypatch.setattr(adventure_updates, "_parse_file", counting_parse)

    # Act
    first = adventure_updates._scan_file(str(tmp_path), "cached.adv")
    again = adventure_updates._scan_file(str(tmp_path), "cached.adv")
    _write_adv(adv, "Second title, longer")
    changed = adventure_updates._scan_file(str(tmp_path), "cached.adv")

    # Assert
    assert first["title"] == "First"
    assert again is first
    assert changed["title"] == "Second title, longer"
    assert len(calls) == 2


def test_session_dir_cleanup_is_throttled(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setitem(session_assets._CLEANUP_STATE, "last_run", None)
    sessions = tmp_path / "adventures" / "sessions"
    stale = sessions / "stale-orphan"
    stale.mkdir(parents=True)
    old = 0
    os.utime(stale, (old, old))

    # Act
    first = session_assets.cleanup_stale_empty_session_dirs(set(), 1, min_interval_seconds=3600)
    stale.mkdir()
    os.utime(stale, (old, old))
    second = session_assets.cleanup_stale_empty_session_dirs(set(), 1, min_interval_seconds=3600)
    unthrottled = session_assets.cleanup_stale_empty_session_dirs(set(), 1)

    # Assert
    assert first == 1
    assert second == 0
    assert unthrottled == 1
