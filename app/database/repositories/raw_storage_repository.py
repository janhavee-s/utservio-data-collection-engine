from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CollectionStatus, RawStorage
from app.database.repositories.base import BaseRepository


class RawStorageRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RawStorage)

    async def get_by_competitor(self, competitor_id: int) -> list[RawStorage]:
        stmt = (
            select(RawStorage)
            .where(RawStorage.competitor_id == competitor_id)
            .order_by(RawStorage.collected_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_url(self, competitor_id: int, source_url: str) -> RawStorage | None:
        stmt = select(RawStorage).where(
            RawStorage.competitor_id == competitor_id,
            RawStorage.source_url == source_url,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest(self, competitor_id: int) -> RawStorage | None:
        stmt = (
            select(RawStorage)
            .where(RawStorage.competitor_id == competitor_id)
            .order_by(RawStorage.id.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self,
        competitor_id: int,
        source_url: str,
        content_hash: str,
        raw_html: str | None = None,
        raw_json: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        collection_status: CollectionStatus = CollectionStatus.SUCCESS,
    ) -> RawStorage:
        """Insert or update raw storage based on URL.

        Uses PostgreSQL ON CONFLICT for atomic upsert to avoid race conditions.
        """
        stmt = (
            insert(RawStorage)
            .values(
                competitor_id=competitor_id,
                source_url=source_url,
                content_hash=content_hash,
                raw_html=raw_html,
                raw_json=raw_json,
                metadata_=metadata,
                collection_status=collection_status,
            )
            .on_conflict_do_update(
                index_elements=["competitor_id", "source_url"],
                set_={
                    "content_hash": content_hash,
                    "raw_html": raw_html,
                    "raw_json": raw_json,
                    "metadata": metadata,
                    "collection_status": collection_status,
                    "collected_at": datetime.now(UTC),
                },
            )
            .returning(RawStorage)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def delete_by_competitor(self, competitor_id: int) -> None:
        from sqlalchemy import delete

        stmt = delete(RawStorage).where(
            RawStorage.competitor_id == competitor_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
