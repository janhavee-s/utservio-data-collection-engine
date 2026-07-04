import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.repositories.competitor_content_repository import CompetitorContentRepository
from app.parsers.strategies.shared import is_valid_content_title
from app.parsers.strategy_parser import StrategyParser
from app.utilities.content_hasher import compute_content_item_hash
from app.utilities.url_normalizer import normalize_content_url

logger = structlog.get_logger(__name__)


class ContentCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()
        log = logger.bind(competitor_id=competitor_id, url=url, module="content")

        try:
            result = await self.fetch(url)
            html = result.html

            if not html or result.not_modified:
                log.info("content_skip", reason="304" if result.not_modified else "empty_html")
                return {
                    "status": "skipped",
                    "reason": "304_not_modified" if result.not_modified else "empty_html",
                    "content_created": 0,
                    "content_updated": 0,
                    "elapsed_seconds": self._elapsed(start_time),
                }

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "content")
            content_items = parsed["content"]

            # Filter out invalid content
            valid_items = []
            skipped_items: list[str] = []
            for item in content_items:
                title = item.get("title", "")
                if is_valid_content_title(title):
                    valid_items.append(item)
                else:
                    skipped_items.append(title)

            if skipped_items:
                log.info(
                    "content_filtered",
                    skipped_count=len(skipped_items),
                    skipped_titles=skipped_items[:10],
                )

            content_repo = CompetitorContentRepository(session)
            content_created = 0
            content_updated = 0
            for item in valid_items:
                item_url = normalize_content_url(item.get("url", url), base_url=url)
                title = item.get("title", "Untitled")
                author = item.get("author")
                content_type = item.get("content_type")

                content_hash = compute_content_item_hash(
                    title, item_url, author, content_type=content_type
                )

                _, was_created = await content_repo.upsert(
                    competitor_id=competitor_id,
                    content_hash=content_hash,
                    title=title,
                    url=item_url,
                    author=author,
                    summary=item.get("summary"),
                    content_type=content_type,
                )
                if was_created:
                    content_created += 1
                else:
                    content_updated += 1

            log.info(
                "content_collected",
                raw_found=len(content_items),
                valid=len(valid_items),
                created=content_created,
                updated=content_updated,
                elapsed=self._elapsed(start_time),
            )

            return {
                "status": "success",
                "content_found": len(valid_items),
                "content_created": content_created,
                "content_updated": content_updated,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            log.error("content_collection_failed", error=str(e), elapsed=self._elapsed(start_time))
            return {
                "status": "failed",
                "error": str(e),
                "content_found": 0,
                "content_created": 0,
                "content_updated": 0,
                "elapsed_seconds": self._elapsed(start_time),
            }
