from __future__ import annotations

from pathlib import Path

from wowlogs_agent.infrastructure.cache.filesystem_response_cache import FilesystemResponseCache


def test_get_returns_none_on_miss(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    assert cache.get("ns", "missing") is None


def test_round_trip_preserves_payload(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    payload = {"data": {"fights": [1, 2, 3]}, "nested": {"k": "v"}}

    cache.put("reportABC/queries", "deadbeef", payload)
    result = cache.get("reportABC/queries", "deadbeef")

    assert result == payload


def test_put_creates_nested_namespace_directories(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    cache.put("a/b/c", "key", {"x": 1})

    assert (tmp_path / "a" / "b" / "c" / "key.json").is_file()


def test_namespaces_are_isolated(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    cache.put("ns1", "k", {"v": 1})
    cache.put("ns2", "k", {"v": 2})

    assert cache.get("ns1", "k") == {"v": 1}
    assert cache.get("ns2", "k") == {"v": 2}


def test_backslashes_in_namespace_are_normalized(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    cache.put("a\\b", "k", {"v": 1})
    assert cache.get("a/b", "k") == {"v": 1}


def test_put_overwrites_existing_entry(tmp_path: Path) -> None:
    cache = FilesystemResponseCache(tmp_path)
    cache.put("ns", "k", {"v": 1})
    cache.put("ns", "k", {"v": 2})
    assert cache.get("ns", "k") == {"v": 2}
