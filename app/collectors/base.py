import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.collectors.fetcher import FetchResult, HybridFetcher
from app.utilities.performance import ContentDeduplicator, URLDeduplicator

logger = logging.getLogger(__name__)

_shared_fetcher: HybridFetcher | None = None

# Shared deduplicators across all collectors
_url_deduplicator = URLDeduplicator()
_content_deduplicator = ContentDeduplicator()


def get_shared_fetcher() -> HybridFetcher:
    """Get or create a shared HybridFetcher instance.

    Sharing the fetcher across collectors ensures:
    - Single httpx.AsyncClient connection pool
    - Single Playwright browser instance
    - Consistent rate limiting across all collectors
    """
    global _shared_fetcher
    if _shared_fetcher is None:
        _shared_fetcher = HybridFetcher()
    return _shared_fetcher


class BaseCollector(ABC):
    def __init__(self, fetcher: HybridFetcher | None = None) -> None:
        self._fetcher = fetcher or get_shared_fetcher()
        self._url_deduplicator = _url_deduplicator
        self._content_deduplicator = _content_deduplicator

    async def close(self) -> None:
        await self._fetcher.close()

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a page using hybrid strategy (httpx + Playwright fallback)."""
        return await self._fetcher.fetch(url)

    def is_duplicate_url(self, url: str) -> bool:
        """Check if URL has been seen before."""
        return self._url_deduplicator.is_duplicate(url)

    def mark_url_seen(self, url: str) -> None:
        """Mark URL as seen."""
        self._url_deduplicator.mark_seen(url)

    def is_duplicate_content(self, content_hash: str, url: str) -> bool:
        """Check if content hash has been seen before for a different URL."""
        return self._content_deduplicator.is_duplicate(content_hash, url)

    def mark_content_seen(self, content_hash: str, url: str) -> None:
        """Mark content hash as seen for a URL."""
        self._content_deduplicator.register(content_hash, url)

    async def store_raw(
        self,
        competitor_id: int,
        url: str,
        html: str,
        session: Any,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        from app.database.repositories.raw_storage_repository import RawStorageRepository
        from app.utilities.content_hasher import compute_page_content_hash
        from app.utilities.url_normalizer import normalize_url

        normalized_url = normalize_url(url)
        content_hash = compute_page_content_hash(html, normalized_url)

        raw_repo = RawStorageRepository(session)
        await raw_repo.upsert(
            competitor_id=competitor_id,
            source_url=normalized_url,
            content_hash=content_hash,
            raw_html=html,
            raw_json={"url": normalized_url, "content_hash": content_hash},
            metadata=metadata,
        )

    @abstractmethod
    async def collect(
        self, competitor_id: int, url: str, *, session: Any, **kwargs: Any
    ) -> dict[str, Any]: ...

    async def collect_with_session(
        self, competitor_id: int, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        from app.database.connection import db_manager

        async with db_manager.session() as session:
            return await self.collect(competitor_id, url, session=session, **kwargs)

    def _elapsed(self, start: float) -> float:
        return round(time.time() - start, 2)
