from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorSocial, SocialPlatform
from app.database.repositories.base import BaseRepository


class CompetitorSocialRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorSocial)

    async def get_by_competitor(self, competitor_id: int) -> list[CompetitorSocial]:
        stmt = (
            select(CompetitorSocial)
            .where(CompetitorSocial.competitor_id == competitor_id)
            .order_by(CompetitorSocial.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_platform(
        self, competitor_id: int, platform: SocialPlatform
    ) -> CompetitorSocial | None:
        stmt = select(CompetitorSocial).where(
            CompetitorSocial.competitor_id == competitor_id,
            CompetitorSocial.platform == platform,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        competitor_id: int,
        platform: SocialPlatform,
        profile_url: str,
        username: str | None = None,
    ) -> tuple[CompetitorSocial, bool]:
        """Insert or update a social profile using atomic PostgreSQL upsert."""
        stmt = (
            insert(CompetitorSocial)
            .values(
                competitor_id=competitor_id,
                platform=platform,
                profile_url=profile_url,
                username=username,
            )
            .on_conflict_do_update(
                index_elements=["competitor_id", "platform"],
                set_={
                    "profile_url": profile_url,
                    "username": username,
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(CompetitorSocial)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return row, row.profile_url == profile_url

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(CompetitorSocial).where(
            CompetitorSocial.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
