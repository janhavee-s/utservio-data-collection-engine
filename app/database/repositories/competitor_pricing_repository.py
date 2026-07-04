from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        """Insert or update a pricing entry using atomic PostgreSQL upsert."""
        stmt = (
            insert(CompetitorPricing)
            .values(
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
            .on_conflict_do_update(
                index_elements=["competitor_id", "service_name"],
                set_={
                    "category": category,
                    "base_price": base_price,
                    "promotional_price": promotional_price,
                    "currency": currency,
                    "discount": discount,
                    "membership_pricing": membership_pricing,
                    "subscription_plans": subscription_plans or [],
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(CompetitorPricing)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return row, row.content_hash == content_hash

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(CompetitorPricing).where(
            CompetitorPricing.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
