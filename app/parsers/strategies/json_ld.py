import json
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import (
    SOCIAL_PLATFORM_DOMAINS,
    detect_countries,
    detect_currency_from_url,
    is_valid_content_title,
    is_valid_service_name,
    parse_price,
)
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
            self._extract_service(item, result, url)
        elif item_type in ("Product", "Offer"):
            self._extract_product(item, result, url)
        elif item_type in ("Article", "BlogPosting", "NewsArticle"):
            self._extract_article(item, result, url)
        elif item_type in ("WebPage", "ContactPage", "AboutPage"):
            self._extract_webpage(item, result, url)
        elif item_type == "ItemList":
            for child in item.get("itemListElement", []):
                if isinstance(child, dict):
                    self._process_item(child, result, url)
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
            if not result.industry:
                area = item.get("areaServed")
                if isinstance(area, str):
                    result.industry = area
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
                result.contact_email = email.replace("mailto:", "")
        if not result.contact_phone:
            phone = item.get("telephone")
            if isinstance(phone, str):
                result.contact_phone = phone.replace("tel:", "")

        # Extract operating countries from areaServed
        area = item.get("areaServed", [])
        if isinstance(area, str):
            area = [area]
        if isinstance(area, list):
            for a in area:
                if isinstance(a, str):
                    countries = detect_countries(a)
                    for c in countries:
                        if c not in result.social_links:
                            result.social_links[f"country:{c}"] = ""

        for key in ("sameAs",):
            urls = item.get(key, [])
            if isinstance(urls, str):
                urls = [urls]
            for link in urls:
                if isinstance(link, str):
                    platform = self._detect_platform(link)
                    if platform and platform not in result.social_links:
                        result.social_links[platform] = link

    def _extract_service(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        name = item.get("name", "")
        if not is_valid_service_name(name):
            return
        duration = item.get("duration") or item.get("estimatedDuration")
        provider = item.get("provider", {})
        provider_name = provider.get("name") if isinstance(provider, dict) else None
        category = item.get("category") or provider_name
        currency = detect_currency_from_url(url)

        # Extract price from offers if present
        offers = item.get("offers", {})
        starting_price = None
        if isinstance(offers, dict):
            price_val = offers.get("price") or offers.get("lowPrice")
            starting_price = parse_price(str(price_val)) if price_val else None
        elif isinstance(offers, list) and offers:
            first_offer = offers[0]
            if isinstance(first_offer, dict):
                price_val = first_offer.get("price") or first_offer.get("lowPrice")
                starting_price = parse_price(str(price_val)) if price_val else None

        result.services.append(
            {
                "name": name,
                "description": item.get("description"),
                "category": category,
                "starting_price": starting_price,
                "currency": currency,
                "estimated_duration": str(duration) if duration else None,
            }
        )

    def _extract_product(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        name = item.get("name", "")
        if not is_valid_service_name(name):
            return
        offers = item.get("offers", {})
        currency = detect_currency_from_url(url)
        if isinstance(offers, dict):
            price = offers.get("price") or offers.get("lowPrice")
            offer_currency = offers.get("priceCurrency", currency)
            if offer_currency and offer_currency != "USD":
                currency = offer_currency
            promotional_price = offers.get("salePrice")
            base_price = parse_price(str(price)) if price else None
            promo_price = parse_price(str(promotional_price)) if promotional_price else None
            discount = None
            if base_price and promo_price and base_price > 0:
                discount = round((1 - promo_price / base_price) * 100, 1)

            result.pricing.append(
                {
                    "service_name": name,
                    "category": item.get("category"),
                    "base_price": base_price,
                    "promotional_price": promo_price,
                    "currency": currency,
                    "discount": discount,
                    "subscription_plans": {},
                    "membership_pricing": None,
                }
            )

    def _extract_article(self, item: dict[str, Any], result: ParsedResult, url: str) -> None:
        title = item.get("headline") or item.get("name")
        if not is_valid_content_title(title):
            return
        article_url = item.get("url")
        if article_url:
            article_url = urljoin(url, article_url)
        else:
            article_url = url
        result.content.append(
            {
                "title": title,
                "author": self._extract_author(item),
                "publish_date": item.get("datePublished"),
                "url": article_url,
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
        if isinstance(author, list) and author:
            first = author[0]
            if isinstance(first, dict):
                return first.get("name")
            if isinstance(first, str):
                return first
        return None

    def _detect_platform(self, url: str) -> str | None:
        for domain, platform in SOCIAL_PLATFORM_DOMAINS.items():
            if domain in url:
                return platform
        return None
