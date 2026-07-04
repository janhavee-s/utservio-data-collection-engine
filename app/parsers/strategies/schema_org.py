from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import (
    SOCIAL_PLATFORM_DOMAINS,
    detect_currency_from_url,
    is_valid_service_name,
    parse_price,
)
from app.parsers.strategy import ParsedResult, ParsingStrategy

SCHEMA_ORG_TYPES = {
    "http://schema.org/LocalBusiness",
    "http://schema.org/Organization",
    "http://schema.org/Corporation",
    "http://schema.org/Company",
    "http://schema.org/Service",
    "http://schema.org/Product",
    "http://schema.org/Offer",
    "http://schema.org/Article",
    "http://schema.org/BlogPosting",
    "http://schema.org/WebPage",
    "http://schema.org/ContactPage",
    "https://schema.org/LocalBusiness",
    "https://schema.org/Organization",
    "https://schema.org/Corporation",
    "https://schema.org/Company",
    "https://schema.org/Service",
    "https://schema.org/Product",
    "https://schema.org/Offer",
    "https://schema.org/Article",
    "https://schema.org/BlogPosting",
    "https://schema.org/WebPage",
    "https://schema.org/ContactPage",
}


class SchemaOrgStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "schema_org"

    @property
    def weight(self) -> float:
        return 0.25

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        for element in soup.select("[itemscope]"):
            itemtype = str(element.get("itemtype", ""))
            if itemtype in SCHEMA_ORG_TYPES:
                self._extract_item(element, itemtype, result, url)
        return result

    def _extract_item(self, element: Any, itemtype: str, result: ParsedResult, url: str) -> None:
        props = self._get_properties(element)
        if (
            "LocalBusiness" in itemtype
            or "Organization" in itemtype
            or "Corporation" in itemtype
            or "Company" in itemtype
        ):
            self._extract_organization(props, result, url)
        elif "Service" in itemtype:
            self._extract_service(props, result, url)
        elif "Product" in itemtype or "Offer" in itemtype:
            self._extract_product(props, result, url)
        elif "Article" in itemtype or "BlogPosting" in itemtype:
            self._extract_article(props, result, url)

    def _extract_service(
        self, props: dict[str, list[str]], result: ParsedResult, url: str
    ) -> None:
        name = props.get("name", [""])[0] if props.get("name") else ""
        if not is_valid_service_name(name):
            return
        duration = (
            (props.get("duration", [None])[0] if props.get("duration") else None)
            or (
                props.get("estimatedDuration", [None])[0]
                if props.get("estimatedDuration")
                else None
            )
        )
        currency = detect_currency_from_url(url)
        result.services.append(
            {
                "name": name,
                "description": (
                    props.get("description", [None])[0] if props.get("description") else None
                ),
                "category": props.get("category", [None])[0] if props.get("category") else None,
                "starting_price": None,
                "currency": currency,
                "estimated_duration": str(duration) if duration else None,
            }
        )

    def _extract_product(
        self, props: dict[str, list[str]], result: ParsedResult, url: str
    ) -> None:
        name = props.get("name", [""])[0] if props.get("name") else ""
        if not is_valid_service_name(name):
            return
        price_text = props.get("price", [None])[0] if props.get("price") else None
        promo_text = (
            props.get("lowPrice", [None])[0]
            if props.get("lowPrice")
            else (props.get("salePrice", [None])[0] if props.get("salePrice") else None)
        )
        base_price = parse_price(price_text)
        promo_price = parse_price(promo_text)
        discount = None
        if base_price and promo_price and base_price > 0:
            discount = round((1 - promo_price / base_price) * 100, 1)

        currency = detect_currency_from_url(url)
        price_currency = (
            props.get("priceCurrency", [None])[0] if props.get("priceCurrency") else None
        )
        if price_currency and price_currency != "USD":
            currency = price_currency

        result.pricing.append(
            {
                "service_name": name,
                "category": props.get("category", [None])[0] if props.get("category") else None,
                "base_price": base_price,
                "promotional_price": promo_price,
                "currency": currency,
                "discount": discount,
                "subscription_plans": {},
                "membership_pricing": None,
            }
        )

    def _extract_article(
        self, props: dict[str, list[str]], result: ParsedResult, url: str
    ) -> None:
        title = props.get("headline", [None])[0] if props.get("headline") else None
        if not title:
            title = props.get("name", [None])[0] if props.get("name") else None
        if not title or len(title) < 5:
            return
        article_url = props.get("url", [url])[0] if props.get("url") else url
        result.content.append(
            {
                "title": title,
                "author": props.get("author", [None])[0] if props.get("author") else None,
                "publish_date": (
                    props.get("datePublished", [None])[0] if props.get("datePublished") else None
                ),
                "url": urljoin(url, article_url),
                "summary": (
                    props.get("description", [None])[0] if props.get("description") else None
                ),
                "content_type": "article",
            }
        )

    def _get_properties(self, element: Any) -> dict[str, list[str]]:
        props: dict[str, list[str]] = {}
        for prop in element.select("[itemprop]"):
            name = prop.get("itemprop", "")
            value = prop.get("content") or prop.get("href") or prop.get_text(strip=True)
            if value:
                props.setdefault(name, []).append(value)
        return props

    def _extract_organization(
        self, props: dict[str, list[str]], result: ParsedResult, url: str
    ) -> None:
        if not result.company_name and props.get("name"):
            result.company_name = props["name"][0]
        if not result.description and props.get("description"):
            result.description = props["description"][0]
        if not result.logo and props.get("logo"):
            result.logo = urljoin(url, props["logo"][0])
        if not result.headquarters and props.get("address"):
            addr = props["address"][0]
            if isinstance(addr, list):
                addr = addr[0] if addr else ""
            result.headquarters = str(addr) if addr else None
        if not result.contact_email and props.get("email"):
            result.contact_email = props["email"][0]
        if not result.contact_phone and props.get("telephone"):
            result.contact_phone = props["telephone"][0]
        if props.get("sameAs"):
            for link in props["sameAs"]:
                platform = self._detect_platform(link)
                if platform and platform not in result.social_links:
                    result.social_links[platform] = link

    def _detect_platform(self, url: str) -> str | None:
        for domain, platform in SOCIAL_PLATFORM_DOMAINS.items():
            if domain in url:
                return platform
        return None
