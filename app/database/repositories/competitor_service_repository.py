from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorService
from app.database.repositories.base import BaseRepository


class CompetitorServiceRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorService)

    async def get_by_competitor(self, competitor_id: int) -> list[CompetitorService]:
        stmt = (
            select(CompetitorService)
            .where(CompetitorService.competitor_id == competitor_id)
            .order_by(CompetitorService.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(self, competitor_id: int, category: str) -> list[CompetitorService]:
        stmt = (
            select(CompetitorService)
            .where(
                CompetitorService.competitor_id == competitor_id,
                CompetitorService.service_category == category,
            )
            .order_by(CompetitorService.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        competitor_id: int,
        content_hash: str,
        service_name: str,
        service_category: str | None = None,
        description: str | None = None,
        estimated_duration: str | None = None,
        starting_price: float | None = None,
        currency: str = "USD",
        available_add_ons: list[object] | None = None,
        membership_available: bool = False,
        offers: list[object] | None = None,
        discounts: list[object] | None = None,
    ) -> tuple[CompetitorService, bool]:
        """Insert or update a service using atomic PostgreSQL upsert."""
        stmt = (
            insert(CompetitorService)
            .values(
                competitor_id=competitor_id,
                content_hash=content_hash,
                service_name=service_name,
                service_category=service_category,
                description=description,
                estimated_duration=estimated_duration,
                starting_price=starting_price,
                currency=currency,
                available_add_ons=available_add_ons or [],
                membership_available=membership_available,
                offers=offers or [],
                discounts=discounts or [],
            )
            .on_conflict_do_update(
                index_elements=["competitor_id", "content_hash"],
                set_={
                    "service_name": service_name,
                    "service_category": service_category,
                    "description": description,
                    "estimated_duration": estimated_duration,
                    "starting_price": starting_price,
                    "currency": currency,
                    "available_add_ons": available_add_ons or [],
                    "membership_available": membership_available,
                    "offers": offers or [],
                    "discounts": discounts or [],
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(CompetitorService)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return row, row.content_hash == content_hash

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(CompetitorService).where(
            CompetitorService.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
