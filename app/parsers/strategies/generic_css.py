from typing import ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import detect_currency, parse_price
from app.parsers.strategy import ParsedResult, ParsingStrategy


class GenericCssPatternStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "generic_css_pattern"

    @property
    def weight(self) -> float:
        return 0.10

    CSS_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "service": [
            "[class*='service']",
            "[class*='product']",
            "[class*='offering']",
            "[class*='feature']",
        ],
        "pricing": [
            "[class*='pricing']",
            "[class*='plan']",
            "[class*='tier']",
            "[class*='package']",
            "[class*='subscription']",
            "[class*='rate']",
        ],
        "content": [
            "[class*='blog']",
            "[class*='article']",
            "[class*='post']",
            "[class*='news']",
        ],
        "company": [
            "[class*='about']",
            "[class*='company']",
            "[class*='team']",
        ],
    }

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        self._extract_services(soup, result)
        self._extract_pricing(soup, result)
        self._extract_content(soup, result, url)
        self._extract_company(soup, result, url)
        return result

    def _extract_services(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        for pattern in self.CSS_PATTERNS["service"]:
            for card in soup.select(pattern):
                name = self._text(card, "h2, h3, h4, h5, .name, .title")
                if not name:
                    continue
                desc_el = card.select_one("p, .description, .desc, .summary")
                result.services.append(
                    {
                        "name": name,
                        "description": desc_el.get_text(strip=True) if desc_el else None,
                        "category": None,
                        "starting_price": None,
                        "currency": "USD",
                        "estimated_duration": None,
                    }
                )

    def _extract_pricing(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        for pattern in self.CSS_PATTERNS["pricing"]:
            for card in soup.select(pattern):
                name = self._text(card, "h2, h3, h4, h5, .name, .title, .plan-name")
                if not name:
                    continue
                price_text = self._text(
                    card, "[class*='price'], [class*='amount'], [class*='cost']"
                )
                result.pricing.append(
                    {
                        "service_name": name,
                        "category": None,
                        "base_price": parse_price(price_text),
                        "promotional_price": None,
                        "currency": detect_currency(price_text),
                        "discount": None,
                        "subscription_plans": {},
                        "membership_pricing": None,
                    }
                )

    def _extract_content(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for pattern in self.CSS_PATTERNS["content"]:
            for card in soup.select(pattern):
                title = self._text(card, "h2, h3, h4, .title, .headline")
                if not title:
                    continue
                link_el = card.select_one("a[href]")
                link = str(link_el.get("href", "")) if link_el else None
                summary_el = card.select_one("p, .summary, .excerpt")
                result.content.append(
                    {
                        "title": title,
                        "author": None,
                        "publish_date": None,
                        "url": urljoin(url, link) if link else None,
                        "summary": summary_el.get_text(strip=True) if summary_el else None,
                        "content_type": "article",
                    }
                )

    def _extract_company(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for pattern in self.CSS_PATTERNS["company"]:
            for card in soup.select(pattern):
                if not result.description:
                    desc_el = card.select_one("p, .description, .about")
                    if desc_el:
                        result.description = desc_el.get_text(strip=True)
