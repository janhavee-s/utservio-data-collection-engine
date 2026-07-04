from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompetitorCompanyInfo
from app.database.repositories.base import BaseRepository


class CompetitorCompanyInfoRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CompetitorCompanyInfo)

    async def get_by_competitor(self, competitor_id: int) -> CompetitorCompanyInfo | None:
        stmt = select(CompetitorCompanyInfo).where(
            CompetitorCompanyInfo.competitor_id == competitor_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        competitor_id: int,
        content_hash: str,
        logo_url: str | None = None,
        description: str | None = None,
        industry: str | None = None,
        headquarters: str | None = None,
        operating_countries: list[str] | None = None,
        operating_cities: list[str] | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        social_links: dict[str, str] | None = None,
    ) -> tuple[CompetitorCompanyInfo, bool]:
        """Insert or update company info using atomic PostgreSQL upsert."""
        stmt = (
            insert(CompetitorCompanyInfo)
            .values(
                competitor_id=competitor_id,
                content_hash=content_hash,
                logo_url=logo_url,
                description=description,
                industry=industry,
                headquarters=headquarters,
                operating_countries=operating_countries or [],
                operating_cities=operating_cities or [],
                contact_email=contact_email,
                contact_phone=contact_phone,
                social_links=social_links or {},
            )
            .on_conflict_do_update(
                index_elements=["competitor_id"],
                set_={
                    "content_hash": content_hash,
                    "logo_url": logo_url,
                    "description": description,
                    "industry": industry,
                    "headquarters": headquarters,
                    "operating_countries": operating_countries or [],
                    "operating_cities": operating_cities or [],
                    "contact_email": contact_email,
                    "contact_phone": contact_phone,
                    "social_links": social_links or {},
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(CompetitorCompanyInfo)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.scalar_one()
        return row, row.content_hash == content_hash

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(CompetitorCompanyInfo).where(
            CompetitorCompanyInfo.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
