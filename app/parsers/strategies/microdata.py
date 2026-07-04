import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.parsers.strategies.shared import (
    detect_currency_from_url,
    is_valid_service_name,
    parse_price,
)
from app.parsers.strategy import ParsedResult, ParsingStrategy


class MicrodataStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "microdata"

    @property
    def weight(self) -> float:
        return 0.15

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        for element in soup.select("[itemprop]"):
            self._extract_itemprop(element, result, url)
        self._extract_emails(soup, result)
        self._extract_phones(soup, result)
        return result

    def _extract_itemprop(self, element: Any, result: ParsedResult, url: str) -> None:
        prop = element.get("itemprop", "")
        value = (
            element.get("content")
            or element.get("href")
            or element.get("src")
            or element.get_text(strip=True)
        )
        if not value:
            return
        if prop == "name" and not result.company_name:
            result.company_name = value
        elif prop == "description" and not result.description:
            result.description = value
        elif prop == "logo" and not result.logo:
            result.logo = urljoin(url, value)
        elif prop == "email" and not result.contact_email:
            email = value.replace("mailto:", "") if value.startswith("mailto:") else value
            result.contact_email = email
        elif prop == "telephone" and not result.contact_phone:
            result.contact_phone = value.replace("tel:", "") if value.startswith("tel:") else value
        elif prop == "address" and not result.headquarters:
            result.headquarters = str(value) if value else None
        elif prop == "imageUrl" and not result.logo:
            result.logo = urljoin(url, value)
        elif prop == "price":
            self._extract_price_contextual(element, value, result, url)

    def _extract_price_contextual(
        self, element: Any, price_value: str, result: ParsedResult, url: str
    ) -> None:
        """Extract price with contextual service name from parent itemscope or nearest heading."""
        price = parse_price(price_value)
        if not price or price <= 0:
            return
        service_name = self._find_contextual_name(element)
        if not is_valid_service_name(service_name):
            return
        result.pricing.append(
            {
                "service_name": service_name,
                "category": None,
                "base_price": price,
                "promotional_price": None,
                "currency": detect_currency_from_url(url),
                "discount": None,
                "subscription_plans": {},
                "membership_pricing": None,
            }
        )

    def _find_contextual_name(self, element: Any) -> str | None:
        """Find a contextual name for a price element.

        Strategy:
        1. Walk up to parent itemscope and find itemprop='name'
        2. Walk up and find nearest heading (h1-h6)
        3. Walk up and find nearest .name or .title class element
        """
        parent = element.parent
        depth = 0
        while parent and isinstance(parent, Tag) and depth < 15:
            # Check for itemscope with name itemprop
            if parent.has_attr("itemscope"):
                name_el = parent.select_one("[itemprop='name']")
                if name_el:
                    return (
                        name_el.get("content")
                        or name_el.get("href")
                        or name_el.get_text(strip=True)
                    )
            # Check for heading
            for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                heading = parent.select_one(tag)
                if heading:
                    text = heading.get_text(strip=True)
                    if text and len(text) < 200:
                        return text
            # Check for name/title class
            name_el = parent.select_one(
                "[class*='name'], [class*='title'], [class*='heading'], .product-name"
            )
            if name_el and name_el is not element:
                text = name_el.get_text(strip=True)
                if text and len(text) < 200:
                    return text
            parent = parent.parent
            depth += 1
        return None

    def _extract_emails(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.contact_email:
            return
        email_link = soup.select_one("a[href^='mailto:']")
        if email_link:
            result.contact_email = str(email_link["href"]).replace("mailto:", "")
            return
        text = soup.get_text()
        email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        match = re.search(email_pattern, text)
        if match:
            result.contact_email = match.group(0)

    def _extract_phones(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.contact_phone:
            return
        phone_link = soup.select_one("a[href^='tel:']")
        if phone_link:
            result.contact_phone = str(phone_link["href"]).replace("tel:", "")
            return
        text = soup.get_text()
        phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        match = re.search(phone_pattern, text)
        if match:
            result.contact_phone = match.group(0).strip()
