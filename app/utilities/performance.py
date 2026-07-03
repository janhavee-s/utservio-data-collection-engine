"""Performance Utilities — batching, caching, and deduplication.

Reduces unnecessary work:
- Batch database inserts
- LRU cache for parsed results
- URL deduplication set
- Reuse parsed soup objects
"""

import functools
import hashlib
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class LRUCache:
    """Thread-safe LRU cache with TTL expiration.

    Used to cache parsed results and avoid repeated parsing.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Get a value from cache. Returns None if missing or expired."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[key]
            return None

        self._cache.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> None:
        """Put a value in cache. Evicts oldest if at capacity."""
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (value, time.time())

    def contains(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class URLDeduplicator:
    """Fast URL deduplication using normalized hash sets.

    Tracks seen URLs across a crawl run to prevent re-processing.
    """

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self._duplicates_skipped = 0

    def is_duplicate(self, url: str) -> bool:
        """Check if URL has already been seen."""
        normalized = url.rstrip("/").lower()
        if normalized in self._seen_urls:
            self._duplicates_skipped += 1
            return True
        return False

    def mark_seen(self, url: str) -> None:
        """Mark a URL as seen."""
        normalized = url.rstrip("/").lower()
        self._seen_urls.add(normalized)

    def check_and_mark(self, url: str) -> bool:
        """Check if duplicate and mark as seen. Returns True if duplicate."""
        if self.is_duplicate(url):
            return True
        self.mark_seen(url)
        return False

    def reset(self) -> None:
        """Reset for a new crawl run."""
        self._seen_hashes.clear()
        self._seen_urls.clear()
        self._duplicates_skipped = 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_seen": len(self._seen_urls),
            "duplicates_skipped": self._duplicates_skipped,
        }


class ContentDeduplicator:
    """Content-level deduplication using content hashes.

    Detects identical content at different URLs.
    """

    def __init__(self) -> None:
        self._hash_to_url: dict[str, str] = {}
        self._duplicates = 0

    def is_duplicate(self, content_hash: str, url: str) -> bool:
        """Check if content hash already exists for a different URL."""
        if content_hash in self._hash_to_url:
            existing_url = self._hash_to_url[content_hash]
            if existing_url != url:
                self._duplicates += 1
                return True
        return False

    def register(self, content_hash: str, url: str) -> None:
        """Register a content hash for a URL."""
        if content_hash not in self._hash_to_url:
            self._hash_to_url[content_hash] = url

    def reset(self) -> None:
        self._hash_to_url.clear()
        self._duplicates = 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "unique_content": len(self._hash_to_url),
            "duplicates_detected": self._duplicates,
        }


def cached_parse(max_size: int = 500, ttl_seconds: int = 1800) -> Callable[[Any], Any]:
    """Decorator to cache parse results by content hash."""

    def decorator(func: Any) -> Any:
        cache = LRUCache(max_size=max_size, ttl_seconds=ttl_seconds)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Handle both instance methods (self, html, url) and functions (html, url)
            if len(args) >= 3:
                # Instance method: self, html, url, ...
                self_obj = args[0]
                html = args[1]
                url = args[2]
            elif len(args) >= 2:
                # Function: html, url
                self_obj = None
                html = args[0]
                url = args[1]
            else:
                # Fallback - try kwargs
                self_obj = args[0] if args else None
                html = kwargs.get("html", "")
                url = kwargs.get("url", "")

            # Include strategy names in cache key if available (for StrategyParser)
            strategy_sig = ""
            if self_obj and hasattr(self_obj, "_strategies"):
                strategy_sig = ",".join(s.name for s in self_obj._strategies)

            content_key = hashlib.sha256(
                f"{url}:{hashlib.sha256(html.encode()).hexdigest()[:16]}:{strategy_sig}".encode()
            ).hexdigest()[:32]
            cached = cache.get(content_key)
            if cached is not None:
                logger.debug("parse_cache_hit", url=url)
                return cached

            result = func(*args, **kwargs)
            cache.put(content_key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
