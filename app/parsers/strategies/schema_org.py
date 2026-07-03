from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS, parse_price
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
            name = props.get("name", [""])[0] if props.get("name") else ""
            result.services.append(
                {
                    "name": name,
                    "description": (
                        props.get("description", [None])[0] if props.get("description") else None
                    ),
                    "category": props.get("category", [None])[0] if props.get("category") else None,
                    "starting_price": None,
                    "currency": "USD",
                    "estimated_duration": None,
                }
            )
        elif "Product" in itemtype or "Offer" in itemtype:
            name = props.get("name", [""])[0] if props.get("name") else ""
            price_text = props.get("price", [None])[0] if props.get("price") else None
            result.pricing.append(
                {
                    "service_name": name,
                    "category": props.get("category", [None])[0] if props.get("category") else None,
                    "base_price": parse_price(price_text),
                    "promotional_price": None,
                    "currency": (
                        props.get("priceCurrency", ["USD"])[0]
                        if props.get("priceCurrency")
                        else "USD"
                    ),
                    "discount": None,
                    "subscription_plans": {},
                    "membership_pricing": None,
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
            result.headquarters = props["address"][0]
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
