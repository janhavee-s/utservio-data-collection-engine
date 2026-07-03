import json
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS
from app.parsers.strategy import ParsedResult, ParsingStrategy

SCHEMA_ORG_TYPES = {
    "LocalBusiness",
    "Organization",
    "Corporation",
    "Company",
    "Service",
    "Product",
    "Offer",
    "Article",
    "BlogPosting",
    "WebPage",
    "Person",
    "ContactPage",
}


class JsonLdStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "json_ld"

    @property
    def weight(self) -> float:
        return 0.30

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        scripts = soup.select('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                self._process_item(item, result, url)
        return result

    def _process_item(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            item_type = " ".join(item_type)
        if item_type in ("LocalBusiness", "Organization", "Corporation", "Company"):
            self._extract_organization(item, result, url)
        elif item_type in ("Service",):
            self._extract_service(item, result)
        elif item_type in ("Product", "Offer"):
            self._extract_product(item, result)
        elif item_type in ("Article", "BlogPosting"):
            self._extract_article(item, result, url)
        elif item_type in ("WebPage", "ContactPage"):
            self._extract_webpage(item, result, url)
        for child in item.get("hasPart", []):
            if isinstance(child, dict):
                self._process_item(child, result, url)
        for child in item.get("subEvent", []):
            if isinstance(child, dict):
                self._process_item(child, result, url)

    def _extract_organization(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        if not result.company_name:
            result.company_name = item.get("name")
        if not result.description:
            result.description = item.get("description")
        if not result.logo:
            logo = item.get("logo")
            if isinstance(logo, str):
                result.logo = urljoin(url, logo)
            elif isinstance(logo, dict):
                result.logo = urljoin(url, logo.get("url", ""))
        if not result.industry:
            result.industry = item.get("industry")
        if not result.headquarters:
            addr = item.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                    addr.get("addressCountry", ""),
                ]
                result.headquarters = ", ".join(p for p in parts if p)
        if not result.contact_email:
            email = item.get("email")
            if isinstance(email, str):
                result.contact_email = email
        if not result.contact_phone:
            phone = item.get("telephone")
            if isinstance(phone, str):
                result.contact_phone = phone
        for key in ("sameAs",):
            urls = item.get(key, [])
            if isinstance(urls, str):
                urls = [urls]
            for link in urls:
                if isinstance(link, str):
                    platform = self._detect_platform(link)
                    if platform and platform not in result.social_links:
                        result.social_links[platform] = link

    def _extract_service(self, item: dict[str, Any], result: ParsedResult) -> None:
        name = item.get("name", "")
        result.services.append(
            {
                "name": name,
                "description": item.get("description"),
                "category": item.get("category"),
                "starting_price": None,
                "currency": "USD",
                "estimated_duration": None,
            }
        )

    def _extract_product(self, item: dict[str, Any], result: ParsedResult) -> None:
        name = item.get("name", "")
        offers = item.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price")
            currency = offers.get("priceCurrency", "USD")
            result.pricing.append(
                {
                    "service_name": name,
                    "category": item.get("category"),
                    "base_price": float(price) if price else None,
                    "promotional_price": None,
                    "currency": currency,
                    "discount": None,
                    "subscription_plans": {},
                    "membership_pricing": None,
                }
            )

    def _extract_article(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        result.content.append(
            {
                "title": item.get("headline"),
                "author": self._extract_author(item),
                "publish_date": item.get("datePublished"),
                "url": urljoin(url, item.get("url", "")),
                "summary": item.get("description"),
                "content_type": "article",
            }
        )

    def _extract_webpage(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        if not result.company_name:
            result.company_name = item.get("name")
        if not result.description:
            result.description = item.get("description")

    def _extract_author(self, item: dict[str, Any]) -> str | None:
        author = item.get("author")
        if isinstance(author, str):
            return author
        if isinstance(author, dict):
            return author.get("name")
        return None

    def _detect_platform(self, url: str) -> str | None:
        for domain, platform in SOCIAL_PLATFORM_DOMAINS.items():
            if domain in url:
                return platform
        return None
