"""Tests for performance utilities."""

from app.utilities.performance import (
    ContentDeduplicator,
    LRUCache,
    URLDeduplicator,
    cached_parse,
)


class TestLRUCache:
    def test_put_and_get(self) -> None:
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_evicts_oldest(self) -> None:
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_get_returns_none_for_missing(self) -> None:
        cache = LRUCache()
        assert cache.get("missing") is None

    def test_contains(self) -> None:
        cache = LRUCache()
        cache.put("key", "value")
        assert cache.contains("key") is True
        assert cache.contains("missing") is False

    def test_clear(self) -> None:
        cache = LRUCache()
        cache.put("a", 1)
        cache.clear()
        assert cache.size == 0

    def test_update_existing_key(self) -> None:
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("a", 2)
        assert cache.get("a") == 2
        assert cache.size == 1


class TestURLDeduplicator:
    def test_check_and_mark(self) -> None:
        dedup = URLDeduplicator()
        assert dedup.check_and_mark("https://example.com/a") is False
        assert dedup.check_and_mark("https://example.com/a") is True
        assert dedup.check_and_mark("https://example.com/b") is False

    def test_is_duplicate(self) -> None:
        dedup = URLDeduplicator()
        dedup.mark_seen("https://example.com")
        assert dedup.is_duplicate("https://example.com") is True

    def test_stats(self) -> None:
        dedup = URLDeduplicator()
        dedup.check_and_mark("https://a.com")
        dedup.check_and_mark("https://a.com")
        dedup.check_and_mark("https://b.com")
        stats = dedup.stats
        assert stats["total_seen"] == 2
        assert stats["duplicates_skipped"] == 1

    def test_reset(self) -> None:
        dedup = URLDeduplicator()
        dedup.check_and_mark("https://a.com")
        dedup.reset()
        assert dedup.stats["total_seen"] == 0


class TestContentDeduplicator:
    def test_is_duplicate(self) -> None:
        dedup = ContentDeduplicator()
        dedup.register("hash1", "https://a.com")
        assert dedup.is_duplicate("hash1", "https://b.com") is True
        assert dedup.is_duplicate("hash1", "https://a.com") is False

    def test_register(self) -> None:
        dedup = ContentDeduplicator()
        dedup.register("hash1", "https://a.com")
        assert dedup.is_duplicate("hash1", "https://b.com") is True

    def test_stats(self) -> None:
        dedup = ContentDeduplicator()
        dedup.register("h1", "https://a.com")
        dedup.is_duplicate("h1", "https://b.com")
        stats = dedup.stats
        assert stats["unique_content"] == 1
        assert stats["duplicates_detected"] == 1


class TestCachedParse:
    def test_caches_result(self) -> None:
        call_count = 0

        @cached_parse(max_size=10, ttl_seconds=3600)
        def parse_fn(html: str, url: str) -> str:
            nonlocal call_count
            call_count += 1
            return "parsed"

        result1 = parse_fn("<html>a</html>", "https://example.com")
        result2 = parse_fn("<html>a</html>", "https://example.com")
        assert result1 == "parsed"
        assert result2 == "parsed"
        assert call_count == 1
