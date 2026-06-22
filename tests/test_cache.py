"""LRU cache tests."""

from app.cache import LRUCache


def test_get_miss_returns_none():
    cache: LRUCache[str, int] = LRUCache(maxsize=2)
    assert cache.get("absent") is None


def test_put_and_get():
    cache: LRUCache[str, int] = LRUCache(maxsize=2)
    cache.put("a", 1)
    assert cache.get("a") == 1


def test_evicts_least_recently_used():
    cache: LRUCache[str, int] = LRUCache(maxsize=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # touch "a" so "b" becomes least-recently-used
    cache.put("c", 3)  # evicts "b"
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert len(cache) == 2
