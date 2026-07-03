import time
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.fetcher import FetchResult, HybridFetcher

_shared_fetcher: HybridFetcher | None = None


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

    async def close(self) -> None:
        await self._fetcher.close()

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a page using hybrid strategy (httpx + Playwright fallback)."""
        return await self._fetcher.fetch(url)

    async def store_raw(
        self,
        competitor_id: int,
        url: str,
        html: str,
        session: AsyncSession,
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
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]: ...

    def _elapsed(self, start: float) -> float:
        return round(time.time() - start, 2)
