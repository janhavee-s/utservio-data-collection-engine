from sqlalchemy import select
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
        """Insert or update a social profile.

        Returns (row, was_created) where was_created is True if a new record was inserted.
        """
        existing = await self.get_by_platform(competitor_id, platform)
        if existing:
            existing.profile_url = profile_url
            existing.username = username
            await self._session.flush()
            return existing, False
        row = await self.create(
            competitor_id=competitor_id,
            platform=platform,
            profile_url=profile_url,
            username=username,
        )
        return row, True

    async def delete_by_competitor(self, competitor_id: int) -> None:
        profiles = await self.get_by_competitor(competitor_id)
        for profile in profiles:
            await self._session.delete(profile)
        await self._session.flush()
