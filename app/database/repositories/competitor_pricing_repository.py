from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorPricing
from app.database.repositories.base import BaseRepository


class CompetitorPricingRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorPricing)

    async def get_by_competitor(self, competitor_id: int) -> list[CompetitorPricing]:
        stmt = (
            select(CompetitorPricing)
            .where(CompetitorPricing.competitor_id == competitor_id)
            .order_by(CompetitorPricing.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(self, competitor_id: int, category: str) -> list[CompetitorPricing]:
        stmt = (
            select(CompetitorPricing)
            .where(
                CompetitorPricing.competitor_id == competitor_id,
                CompetitorPricing.category == category,
            )
            .order_by(CompetitorPricing.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_hash(self, competitor_id: int, content_hash: str) -> CompetitorPricing | None:
        """Find a pricing entry by its content hash within a competitor scope."""
        stmt = select(CompetitorPricing).where(
            CompetitorPricing.competitor_id == competitor_id,
            CompetitorPricing.content_hash == content_hash,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        competitor_id: int,
        content_hash: str,
        service_name: str,
        category: str | None = None,
        base_price: float | None = None,
        promotional_price: float | None = None,
        currency: str = "USD",
        discount: float | None = None,
        membership_pricing: dict[str, object] | None = None,
        subscription_plans: list[str] | None = None,
    ) -> tuple[CompetitorPricing, bool]:
        """Insert or update a pricing entry based on content hash.

        Returns (row, was_created) where was_created is True if a new record was inserted.
        """
        existing = await self.get_by_hash(competitor_id, content_hash)
        if existing:
            existing.collected_at = datetime.now(UTC)
            await self._session.flush()
            return existing, False
        row = await self.create(
            competitor_id=competitor_id,
            content_hash=content_hash,
            service_name=service_name,
            category=category,
            base_price=base_price,
            promotional_price=promotional_price,
            currency=currency,
            discount=discount,
            membership_pricing=membership_pricing,
            subscription_plans=subscription_plans or [],
        )
        return row, True

    async def delete_by_competitor(self, competitor_id: int) -> None:
        pricing = await self.get_by_competitor(competitor_id)
        for item in pricing:
            await self._session.delete(item)
        await self._session.flush()
