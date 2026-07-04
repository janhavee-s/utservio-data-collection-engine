from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorSource
from app.database.repositories.base import BaseRepository


class CompetitorSourceRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorSource)

    async def get_by_competitor(self, competitor_id: int) -> list[CompetitorSource]:
        stmt = (
            select(CompetitorSource)
            .where(CompetitorSource.competitor_id == competitor_id)
            .order_by(CompetitorSource.discovered_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_competitor(self, competitor_id: int) -> list[CompetitorSource]:
        stmt = (
            select(CompetitorSource)
            .where(
                CompetitorSource.competitor_id == competitor_id,
                CompetitorSource.is_active.is_(True),
            )
            .order_by(CompetitorSource.discovered_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_url(self, competitor_id: int, url: str) -> CompetitorSource | None:
        stmt = select(CompetitorSource).where(
            CompetitorSource.competitor_id == competitor_id,
            CompetitorSource.url == url,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        competitor_id: int,
        url: str,
        page_type: str | None = None,
    ) -> CompetitorSource:
        """Insert or update a source using atomic PostgreSQL upsert."""
        stmt = (
            insert(CompetitorSource)
            .values(
                competitor_id=competitor_id,
                url=url,
                page_type=page_type,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["competitor_id", "url"],
                set_={
                    "page_type": page_type,
                    "last_crawled_at": datetime.now(UTC),
                    "is_active": True,
                },
            )
            .returning(CompetitorSource)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def deactivate(self, source_id: int) -> CompetitorSource | None:
        return await self.update(source_id, is_active=False)

    async def mark_crawled(self, source_id: int) -> CompetitorSource | None:
        return await self.update(source_id, last_crawled_at=datetime.now(UTC))
