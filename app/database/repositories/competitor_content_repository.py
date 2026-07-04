from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        """Insert or update a content item using atomic PostgreSQL upsert on URL."""
        stmt = (
            insert(CompetitorContent)
            .values(
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
            .on_conflict_do_update(
                index_elements=["competitor_id", "url"],
                set_={
                    "content_hash": content_hash,
                    "title": title,
                    "author": author,
                    "publish_date": publish_date,
                    "summary": summary,
                    "raw_content": raw_content,
                    "content_type": content_type,
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(CompetitorContent)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return row, row.content_hash == content_hash

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(CompetitorContent).where(
            CompetitorContent.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
