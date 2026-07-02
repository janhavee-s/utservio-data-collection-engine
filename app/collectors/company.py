import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.parsers.strategy_parser import StrategyParser


class CompanyCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()

        try:
            result = await self.fetch(url)
            html = result.html

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "company")

            return {
                "status": "success",
                "company_data": parsed,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "company_data": {},
                "elapsed_seconds": self._elapsed(start_time),
            }
