import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.repositories.competitor_pricing_repository import CompetitorPricingRepository
from app.parsers.strategies.shared import is_valid_pricing_entry
from app.parsers.strategy_parser import StrategyParser
from app.utilities.content_hasher import compute_pricing_hash

logger = structlog.get_logger(__name__)


class PricingCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()
        log = logger.bind(competitor_id=competitor_id, url=url, module="pricing")

        try:
            # Use API interception with city selection to capture pricing data
            from app.collectors.fetcher import HybridFetcher
            fetcher = HybridFetcher()
            
            api_patterns = [
                "price", "pricing", "plan", "service", "product",
                "api", "graphql", "data", "catalog", "offer",
            ]
            
            # Try city selection first, fall back to regular interception
            result, intercepted_data = await fetcher._fetch_dynamic_with_city_selection(
                url, city="Mumbai", api_patterns=api_patterns
            )
            
            html = result.html

            if not html or result.not_modified:
                log.info("pricing_skip", reason="304" if result.not_modified else "empty_html")
                return {
                    "status": "skipped",
                    "reason": "304_not_modified" if result.not_modified else "empty_html",
                    "pricing_created": 0,
                    "pricing_updated": 0,
                    "elapsed_seconds": self._elapsed(start_time),
                }

            await self.store_raw(competitor_id, url, html, session)

            # Parse HTML for pricing
            parsed = self._parser.parse_for_type(html, url, "pricing")
            pricing_items = parsed["pricing"]

            # Extract pricing from intercepted API responses
            api_pricing = self._extract_pricing_from_api(intercepted_data)
            pricing_items.extend(api_pricing)

            # Filter out placeholder pricing entries
            valid_items = []
            skipped_items: list[str] = []
            for item in pricing_items:
                service_name = item.get("service_name", "")
                base_price = item.get("base_price")
                if is_valid_pricing_entry(service_name, base_price):
                    valid_items.append(item)
                else:
                    skipped_items.append(service_name)

            if skipped_items:
                log.info(
                    "pricing_filtered",
                    skipped_count=len(skipped_items),
                    skipped_names=skipped_items[:10],
                )

            pricing_repo = CompetitorPricingRepository(session)
            pricing_created = 0
            pricing_updated = 0
            for item in valid_items:
                service_name = item.get("service_name", "Unknown")
                category = item.get("category")
                base_price = item.get("base_price")
                promotional_price = item.get("promotional_price")
                currency = item.get("currency", "INR")

                content_hash = compute_pricing_hash(
                    service_name, category, base_price, promotional_price, currency
                )

                _, was_created = await pricing_repo.upsert(
                    competitor_id=competitor_id,
                    content_hash=content_hash,
                    service_name=service_name,
                    category=category,
                    base_price=base_price,
                    promotional_price=promotional_price,
                    currency=currency,
                    discount=item.get("discount"),
                    membership_pricing=item.get("membership_pricing"),
                    subscription_plans=item.get("subscription_plans") or [],
                )
                if was_created:
                    pricing_created += 1
                else:
                    pricing_updated += 1

            log.info(
                "pricing_collected",
                raw_found=len(pricing_items),
                valid=len(valid_items),
                created=pricing_created,
                updated=pricing_updated,
                api_intercepted=len(intercepted_data),
                elapsed=self._elapsed(start_time),
            )

            return {
                "status": "success",
                "pricing_found": len(valid_items),
                "pricing_created": pricing_created,
                "pricing_updated": pricing_updated,
                "api_intercepted": len(intercepted_data),
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            log.error("pricing_collection_failed", error=str(e), elapsed=self._elapsed(start_time))
            return {
                "status": "failed",
                "error": str(e),
                "pricing_found": 0,
                "pricing_created": 0,
                "pricing_updated": 0,
                "api_intercepted": 0,
                "elapsed_seconds": self._elapsed(start_time),
            }

    def _extract_pricing_from_api(
        self, intercepted_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract pricing information from intercepted API responses."""
        pricing_items = []
        
        for item in intercepted_data:
            data = item.get("data", {})
            if not isinstance(data, dict):
                continue
            
            # Look for pricing data in common patterns
            pricing_items.extend(self._extract_from_dict(data))
        
        return pricing_items

    def _extract_from_dict(self, data: dict[str, Any], depth: int = 0) -> list[dict[str, Any]]:
        """Recursively extract pricing from a dictionary."""
        if depth > 5:  # Prevent infinite recursion
            return []
        
        pricing_items = []
        
        # Check if this dict has pricing-like fields
        if self._has_pricing_fields(data):
            item = self._parse_pricing_dict(data)
            if item:
                pricing_items.append(item)
        
        # Recurse into nested dicts and lists
        for key, value in data.items():
            if isinstance(value, dict):
                pricing_items.extend(self._extract_from_dict(value, depth + 1))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        pricing_items.extend(self._extract_from_dict(item, depth + 1))
        
        return pricing_items

    def _has_pricing_fields(self, data: dict[str, Any]) -> bool:
        """Check if a dict has pricing-related fields."""
        pricing_keywords = [
            "price", "pricing", "cost", "rate", "amount",
            "service_name", "plan_name", "product_name",
        ]
        return any(keyword in str(data.keys()).lower() for keyword in pricing_keywords)

    def _parse_pricing_dict(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a dict into a pricing item."""
        # Try to find service name
        service_name = None
        for key in ["service_name", "name", "plan_name", "product_name", "title"]:
            if key in data and isinstance(data[key], str):
                service_name = data[key]
                break
        
        if not service_name:
            return None
        
        # Try to find price
        base_price = None
        for key in ["price", "base_price", "amount", "cost", "rate"]:
            if key in data:
                price_val = data[key]
                if isinstance(price_val, (int, float)):
                    base_price = float(price_val)
                elif isinstance(price_val, str):
                    # Try to parse price string
                    import re
                    price_match = re.search(r'[\d,]+\.?\d*', price_val.replace(',', ''))
                    if price_match:
                        base_price = float(price_match.group())
                break
        
        if base_price is None:
            return None
        
        return {
            "service_name": service_name,
            "base_price": base_price,
            "currency": data.get("currency", "INR"),
            "category": data.get("category"),
            "promotional_price": data.get("promotional_price"),
            "discount": data.get("discount"),
            "membership_pricing": data.get("membership_pricing"),
            "subscription_plans": data.get("subscription_plans"),
        }
