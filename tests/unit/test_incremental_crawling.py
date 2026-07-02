"""Tests for incremental crawling and HTTP cache layer."""

import pytest

from app.collectors.fetcher import (
    FetchResult,
    HttpCacheLayer,
    RateLimiter,
)


class TestFetchResult:
    def test_fetch_result_defaults(self) -> None:
        result = FetchResult(html="<html></html>", url="https://example.com", method="httpx")
        assert result.etag is None
        assert result.last_modified is None
        assert result.cache_control is None
        assert result.content_hash == ""
        assert result.not_modified is False
        assert result.language == ""
        assert result.page_type == ""

    def test_fetch_result_with_cache_fields(self) -> None:
        result = FetchResult(
            html="<html></html>",
            url="https://example.com",
            method="httpx",
            etag='"abc123"',
            last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
            cache_control="max-age=3600",
            content_hash="a1b2c3d4",
        )
        assert result.etag == '"abc123"'
        assert result.last_modified == "Wed, 01 Jan 2025 00:00:00 GMT"
        assert result.cache_control == "max-age=3600"
        assert result.content_hash == "a1b2c3d4"

    def test_fetch_result_304_not_modified(self) -> None:
        result = FetchResult(
            html="",
            url="https://example.com",
            method="httpx",
            status_code=304,
            not_modified=True,
            content_hash="abc123",
        )
        assert result.not_modified is True
        assert result.status_code == 304


class TestHttpCacheLayer:
    def test_store_and_retrieve(self) -> None:
        cache = HttpCacheLayer()
        cache.store(
            url="https://example.com",
            etag='"v1"',
            last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
            cache_control="max-age=3600",
            content_hash="hash1",
        )
        entry = cache.get("https://example.com")
        assert entry is not None
        assert entry.etag == '"v1"'
        assert entry.last_modified == "Wed, 01 Jan 2025 00:00:00 GMT"
        assert entry.cache_control == "max-age=3600"
        assert entry.content_hash == "hash1"

    def test_build_conditional_headers_with_etag(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://example.com", etag='"v1"')
        headers = cache.build_conditional_headers("https://example.com")
        assert headers["If-None-Match"] == '"v1"'

    def test_build_conditional_headers_with_last_modified(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://example.com", last_modified="Wed, 01 Jan 2025 00:00:00 GMT")
        headers = cache.build_conditional_headers("https://example.com")
        assert headers["If-Modified-Since"] == "Wed, 01 Jan 2025 00:00:00 GMT"

    def test_build_conditional_headers_empty(self) -> None:
        cache = HttpCacheLayer()
        headers = cache.build_conditional_headers("https://unknown.com")
        assert headers == {}

    def test_is_cache_expired_no_cache_control(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://example.com")
        assert cache.is_cache_expired("https://example.com") is True

    def test_is_cache_expired_no_cache(self) -> None:
        cache = HttpCacheLayer()
        assert cache.is_cache_expired("https://unknown.com") is True

    def test_store_updates_existing(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://example.com", etag='"v1"')
        cache.store(url="https://example.com", etag='"v2"')
        entry = cache.get("https://example.com")
        assert entry is not None
        assert entry.etag == '"v2"'

    def test_remove(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://example.com", etag='"v1"')
        cache.remove("https://example.com")
        assert cache.get("https://example.com") is None

    def test_clear(self) -> None:
        cache = HttpCacheLayer()
        cache.store(url="https://a.com")
        cache.store(url="https://b.com")
        cache.clear()
        assert cache.size == 0


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(self) -> None:
        limiter = RateLimiter(rate=10.0)
        await limiter.acquire()
        assert limiter._tokens < 10.0
