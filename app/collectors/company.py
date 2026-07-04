import time
from typing import Any

import structlog
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.repositories.competitor_company_info_repository import (
    CompetitorCompanyInfoRepository,
)
from app.parsers.strategies.shared import detect_countries, detect_indian_cities
from app.parsers.strategy_parser import StrategyParser
from app.utilities.content_hasher import compute_page_content_hash

logger = structlog.get_logger(__name__)


class CompanyCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()
        log = logger.bind(competitor_id=competitor_id, url=url, module="company")

        try:
            result = await self.fetch(url)
            html = result.html

            if not html or result.not_modified:
                log.info("company_skip", reason="304" if result.not_modified else "empty_html")
                return {
                    "status": "skipped",
                    "reason": "304_not_modified" if result.not_modified else "empty_html",
                    "company_data": {},
                    "elapsed_seconds": self._elapsed(start_time),
                }

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "company")
            company = parsed

            # Enrich with text-based extraction from full HTML
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(separator=" ", strip=True)

            operating_countries = company.get("operating_countries", [])
            if not operating_countries:
                operating_countries = detect_countries(text_content)

            operating_cities = company.get("operating_cities", [])
            if not operating_cities:
                operating_cities = detect_indian_cities(text_content)

            content_hash = compute_page_content_hash(str(company), url)

            company_repo = CompetitorCompanyInfoRepository(session)
            headquarters = company.get("headquarters")
            if isinstance(headquarters, list):
                headquarters = ", ".join(str(h) for h in headquarters if h)
            industry = company.get("industry")
            if isinstance(industry, list):
                industry = ", ".join(str(i) for i in industry if i)
            _, was_created = await company_repo.upsert(
                competitor_id=competitor_id,
                content_hash=content_hash,
                logo_url=company.get("logo"),
                description=company.get("description"),
                industry=industry,
                headquarters=headquarters,
                operating_countries=operating_countries,
                operating_cities=operating_cities,
                contact_email=company.get("contact_email"),
                contact_phone=company.get("contact_phone"),
                social_links=company.get("social_links", {}),
            )

            log.info(
                "company_collected",
                has_logo=bool(company.get("logo")),
                has_description=bool(company.get("description")),
                has_email=bool(company.get("contact_email")),
                has_phone=bool(company.get("contact_phone")),
                social_links_count=len(company.get("social_links", {})),
                operating_countries=operating_countries,
                operating_cities=operating_cities,
                persisted=was_created,
                elapsed=self._elapsed(start_time),
            )

            return {
                "status": "success",
                "company_data": parsed,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            log.error("company_collection_failed", error=str(e), elapsed=self._elapsed(start_time))
            return {
                "status": "failed",
                "error": str(e),
                "company_data": {},
                "elapsed_seconds": self._elapsed(start_time),
            }
