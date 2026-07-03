from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorContent
from app.database.repositories.base import BaseRepository


class CompetitorContentRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorContent)

    async def get_by_competitor(self, competitor_id: int) -> list[CompetitorContent]:
        stmt = (
            select(CompetitorContent)
            .where(CompetitorContent.competitor_id == competitor_id)
            .order_by(CompetitorContent.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(self, competitor_id: int, content_type: str) -> list[CompetitorContent]:
        stmt = (
            select(CompetitorContent)
            .where(
                CompetitorContent.competitor_id == competitor_id,
                CompetitorContent.content_type == content_type,
            )
            .order_by(CompetitorContent.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_url(self, competitor_id: int, url: str) -> CompetitorContent | None:
        stmt = select(CompetitorContent).where(
            CompetitorContent.competitor_id == competitor_id,
            CompetitorContent.url == url,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, competitor_id: int, content_hash: str) -> CompetitorContent | None:
        """Find a content item by its content hash within a competitor scope."""
        stmt = select(CompetitorContent).where(
            CompetitorContent.competitor_id == competitor_id,
            CompetitorContent.content_hash == content_hash,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        competitor_id: int,
        content_hash: str,
        title: str,
        url: str,
        author: str | None = None,
        publish_date: "date | None" = None,
        summary: str | None = None,
        raw_content: str | None = None,
        content_type: str | None = None,
    ) -> tuple[CompetitorContent, bool]:
        """Insert or update a content item based on URL or content hash.

        Returns (row, was_created) where was_created is True if a new record was inserted.
        """
        # Primary: check by URL
        existing = await self.get_by_url(competitor_id, url)
        if existing:
            existing.collected_at = datetime.now(UTC)
            await self._session.flush()
            return existing, False

        # Secondary: check by content hash (same content, different URL)
        existing = await self.get_by_hash(competitor_id, content_hash)
        if existing:
            existing.collected_at = datetime.now(UTC)
            await self._session.flush()
            return existing, False

        row = await self.create(
            competitor_id=competitor_id,
            content_hash=content_hash,
            title=title,
            url=url,
            author=author,
            publish_date=publish_date,
            summary=summary,
            raw_content=raw_content,
            content_type=content_type,
        )
        return row, True

    async def delete_by_competitor(self, competitor_id: int) -> None:
        content = await self.get_by_competitor(competitor_id)
        for item in content:
            await self._session.delete(item)
        await self._session.flush()
