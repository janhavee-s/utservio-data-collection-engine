import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.repositories.competitor_service_repository import CompetitorServiceRepository
from app.parsers.strategies.shared import is_valid_service_name
from app.parsers.strategy_parser import StrategyParser
from app.utilities.content_hasher import compute_service_hash

logger = structlog.get_logger(__name__)


class ServiceCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()
        log = logger.bind(competitor_id=competitor_id, url=url, module="services")

        try:
            result = await self.fetch(url)
            html = result.html

            if not html or result.not_modified:
                log.info("services_skip", reason="304" if result.not_modified else "empty_html")
                return {
                    "status": "skipped",
                    "reason": "304_not_modified" if result.not_modified else "empty_html",
                    "services_created": 0,
                    "services_updated": 0,
                    "elapsed_seconds": self._elapsed(start_time),
                }

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "services")
            services = parsed["services"]

            # Filter out invalid services (FAQ, nav, etc.)
            valid_services = []
            skipped_names: list[str] = []
            for svc in services:
                name = svc.get("name", "")
                if is_valid_service_name(name):
                    valid_services.append(svc)
                else:
                    skipped_names.append(name)

            if skipped_names:
                log.info(
                    "services_filtered",
                    skipped_count=len(skipped_names),
                    skipped_names=skipped_names[:10],
                )

            service_repo = CompetitorServiceRepository(session)
            services_created = 0
            services_updated = 0
            for svc in valid_services:
                service_name = svc.get("name", "Unknown")
                service_category = svc.get("category")
                description = svc.get("description")
                starting_price = svc.get("starting_price")
                currency = svc.get("currency", "INR")

                content_hash = compute_service_hash(
                    service_name, service_category, description, starting_price, currency
                )

                _, was_created = await service_repo.upsert(
                    competitor_id=competitor_id,
                    content_hash=content_hash,
                    service_name=service_name,
                    service_category=service_category,
                    description=description,
                    starting_price=starting_price,
                    currency=currency,
                    estimated_duration=svc.get("estimated_duration"),
                )
                if was_created:
                    services_created += 1
                else:
                    services_updated += 1

            log.info(
                "services_collected",
                raw_found=len(services),
                valid=len(valid_services),
                created=services_created,
                updated=services_updated,
                elapsed=self._elapsed(start_time),
            )

            return {
                "status": "success",
                "services_found": len(valid_services),
                "services_created": services_created,
                "services_updated": services_updated,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            log.error("services_collection_failed", error=str(e), elapsed=self._elapsed(start_time))
            return {
                "status": "failed",
                "error": str(e),
                "services_found": 0,
                "services_created": 0,
                "services_updated": 0,
                "elapsed_seconds": self._elapsed(start_time),
            }
