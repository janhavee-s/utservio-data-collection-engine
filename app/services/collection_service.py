import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.collectors.company import CompanyCollector
from app.collectors.content import ContentCollector
from app.collectors.discovery import DiscoveryEngine
from app.collectors.pricing import PricingCollector
from app.collectors.service import ServiceCollector
from app.collectors.social import SocialCollector
from app.database.connection import db_manager
from app.database.repositories.collection_log_repository import CollectionLogRepository
from app.database.repositories.competitor_repository import CompetitorRepository
from app.database.repositories.competitor_source_repository import CompetitorSourceRepository

logger = structlog.get_logger(__name__)

MODULE_COLLECTORS: dict[str, Any] = {
    "company": CompanyCollector,
    "services": ServiceCollector,
    "pricing": PricingCollector,
    "content": ContentCollector,
    "social": SocialCollector,
}


class CollectionService:
    def __init__(self) -> None:
        self._collectors: dict[str, Any] = {}

    def _get_collector(self, module: str) -> Any:
        if module not in self._collectors:
            collector_cls = MODULE_COLLECTORS.get(module)
            if collector_cls:
                self._collectors[module] = collector_cls()
        return self._collectors.get(module)

    async def collect_competitor(self, competitor_id: int) -> dict[str, Any]:
        start_time = time.time()
        log = logger.bind(competitor_id=competitor_id)

        try:
            async with db_manager.session() as session:
                comp_repo = CompetitorRepository(session)
                competitor = await comp_repo.get_by_id(competitor_id)
                if not competitor:
                    return {"status": "failed", "error": f"Competitor {competitor_id} not found"}

                enabled = getattr(competitor, "enabled", True)
                if not enabled:
                    return {"status": "skipped", "reason": "Competitor disabled"}

                modules = getattr(competitor, "modules", []) or []
                if not modules:
                    return {"status": "skipped", "reason": "No modules configured"}

                base_url = getattr(competitor, "website_url", "")
                source_repo = CompetitorSourceRepository(session)
                log.info("collection_started", modules=modules, base_url=base_url)

                discovery_engine = DiscoveryEngine()
                discovered = await discovery_engine.discover(base_url)

                discovered_urls = [d.url for d in discovered]
                log.info(
                    "discovery_complete",
                    total_urls=len(discovered_urls),
                    sources=self._count_sources(discovered),
                )

                for d in discovered:
                    existing = await source_repo.get_by_url(competitor_id, d.url)
                    if not existing:
                        await source_repo.create(
                            competitor_id=competitor_id,
                            url=d.url,
                            page_type=self._classify_url(d.url),
                        )
                    else:
                        await source_repo.mark_crawled(existing.id)

                results: dict[str, Any] = {}
                errors: list[str] = []
                records_collected = 0
                skipped_urls: list[str] = []

                for module in modules:
                    if module == "discovery":
                        results[module] = [{"status": "completed", "source": "DiscoveryEngine"}]
                        continue

                    collector = self._get_collector(module)
                    if not collector:
                        log.warning("unknown_module", module=module)
                        continue

                    urls_to_fetch = self._select_urls_for_module(module, discovered_urls, base_url)

                    if not urls_to_fetch:
                        log.info("no_urls_for_module", module=module)
                        skipped_urls.append(f"{module}: no matching URLs")
                        results[module] = []
                        continue

                    log.info(
                        "module_fetching_urls",
                        module=module,
                        url_count=len(urls_to_fetch),
                        urls=urls_to_fetch[:5],
                    )

                    module_results = []
                    for url in urls_to_fetch:
                        try:
                            result = await collector.collect(competitor_id, url, session=session)
                            module_results.append(result)
                            if result.get("status") == "success":
                                records_collected += sum(
                                    v for v in result.values() if isinstance(v, int) and v > 0
                                )
                        except Exception as e:
                            log.error(
                                "module_collection_failed",
                                module=module,
                                url=url,
                                error=str(e),
                            )
                            module_results.append({"status": "failed", "error": str(e)})
                            errors.append(f"{module}/{url}: {e!s}")

                    results[module] = module_results

                elapsed = round(time.time() - start_time, 2)

                log_repo = CollectionLogRepository(session)
                await log_repo.create(
                    competitor_id=competitor_id,
                    start_time=datetime.fromtimestamp(start_time, tz=UTC),
                    end_time=datetime.now(UTC),
                    success=len(errors) == 0,
                    duration_seconds=elapsed,
                    records_collected=records_collected,
                    errors=errors,
                    retry_count=0,
                )

                log.info(
                    "collection_completed",
                    elapsed=elapsed,
                    modules=modules,
                    records_collected=records_collected,
                    errors=len(errors),
                )

                return {
                    "status": "success",
                    "competitor_id": competitor_id,
                    "modules_collected": modules,
                    "results": results,
                    "elapsed_seconds": elapsed,
                    "discovered_urls": len(discovered_urls),
                }
        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            log.error("collection_failed", error=str(e), elapsed=elapsed)
            return {
                "status": "failed",
                "competitor_id": competitor_id,
                "error": str(e),
                "elapsed_seconds": elapsed,
            }

    def _select_urls_for_module(
        self, module: str, discovered_urls: list[str], base_url: str
    ) -> list[str]:
        """Select discovered URLs relevant to a module using pattern matching."""
        base = base_url.rstrip("/")
        patterns = {
            "company": [r"/about", r"/company", r"/team", r"/story", r"/mission", r"/contact"],
            "services": [r"/service", r"/product", r"/feature", r"/solution", r"/plan"],
            "pricing": [r"/pric", r"/cost", r"/rate", r"/plan", r"/subscription"],
            "content": [r"/blog", r"/article", r"/news", r"/resource", r"/case-study", r"/post"],
            "social": [r"/social", r"/follow", r"/community"],
        }

        module_patterns = patterns.get(module, [])
        if not module_patterns:
            return [base]

        matched = []
        for url in discovered_urls:
            url_lower = url.lower()
            if any(p in url_lower for p in module_patterns):
                matched.append(url)

        if not matched:
            return [base]

        return matched[:10]

    def _classify_url(self, url: str) -> str:
        """Classify a URL into a page type based on path patterns."""
        url_lower = url.lower()
        if any(p in url_lower for p in ("service", "product", "feature", "solution")):
            return "services"
        if any(p in url_lower for p in ("pric", "cost", "rate", "plan")):
            return "pricing"
        if any(p in url_lower for p in ("blog", "article", "news", "post", "resource")):
            return "content"
        if any(p in url_lower for p in ("about", "company", "team", "contact")):
            return "company"
        if any(p in url_lower for p in ("social", "follow", "community")):
            return "social"
        if "sitemap" in url_lower:
            return "sitemap"
        return "general"

    def _count_sources(self, discovered: list[Any]) -> dict[str, int]:
        """Count discovered URLs by source."""
        counts: dict[str, int] = {}
        for d in discovered:
            counts[d.source] = counts.get(d.source, 0) + 1
        return counts

    async def close(self) -> None:
        for collector in self._collectors.values():
            if hasattr(collector, "close"):
                await collector.close()


collection_service = CollectionService()
