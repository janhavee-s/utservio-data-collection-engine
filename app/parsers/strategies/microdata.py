import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import detect_currency, parse_price
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
        self._extract_prices(soup, result)
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
            result.headquarters = value
        elif prop == "price":
            self._add_price_from_itemprop(value, result)
        elif prop == "imageUrl" and not result.logo:
            result.logo = urljoin(url, value)

    def _add_price_from_itemprop(self, value: str, result: ParsedResult) -> None:
        price = parse_price(value)
        if price is not None:
            result.pricing.append(
                {
                    "service_name": "Detected Service",
                    "category": None,
                    "base_price": price,
                    "promotional_price": None,
                    "currency": detect_currency(value),
                    "discount": None,
                    "subscription_plans": {},
                    "membership_pricing": None,
                }
            )

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

    def _extract_prices(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.pricing:
            return
        text = soup.get_text()
        price_patterns = [
            r"[\$€£₹]\s*\d+(?:,\d{3})*(?:\.\d{2})?",
            r"\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)",
        ]
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:5]:
                price = parse_price(match)
                if price is not None:
                    result.pricing.append(
                        {
                            "service_name": "Detected Price",
                            "category": None,
                            "base_price": price,
                            "promotional_price": None,
                            "currency": detect_currency(match),
                            "discount": None,
                            "subscription_plans": {},
                            "membership_pricing": None,
                        }
                    )
            if result.pricing:
                break
