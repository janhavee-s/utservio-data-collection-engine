import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.repositories.competitor_content_repository import CompetitorContentRepository
from app.parsers.strategy_parser import StrategyParser
from app.utilities.content_hasher import compute_content_item_hash
from app.utilities.url_normalizer import normalize_content_url


class ContentCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()

        try:
            result = await self.fetch(url)
            html = result.html

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "content")
            content_items = parsed["content"]

            content_repo = CompetitorContentRepository(session)
            content_created = 0
            content_updated = 0
            for item in content_items:
                item_url = normalize_content_url(item.get("url", url), base_url=url)
                title = item.get("title", "Untitled")
                author = item.get("author")
                content_type = item.get("content_type")

                content_hash = compute_content_item_hash(
                    title, item_url, author, content_type=content_type
                )

                existing = await content_repo.get_by_url(competitor_id, item_url)
                await content_repo.upsert(
                    competitor_id=competitor_id,
                    content_hash=content_hash,
                    title=title,
                    url=item_url,
                    author=author,
                    summary=item.get("summary"),
                    content_type=content_type,
                )
                if existing:
                    content_updated += 1
                else:
                    content_created += 1

            return {
                "status": "success",
                "content_found": len(content_items),
                "content_created": content_created,
                "content_updated": content_updated,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "content_found": 0,
                "content_created": 0,
                "content_updated": 0,
                "elapsed_seconds": self._elapsed(start_time),
            }
