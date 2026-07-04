from typing import ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.parsers.strategies.shared import (
    detect_currency_from_url,
    is_valid_content_title,
    is_valid_service_name,
    parse_price,
)
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
            "[class*='service-card']",
            "[class*='service-item']",
            "[class*='service-listing']",
            "[class*='product-card']",
            "[class*='product-item']",
            "[class*='offering']",
            "[class*='category-card']",
            "[data-service]",
            "[data-product]",
        ],
        "pricing": [
            "[class*='pricing-card']",
            "[class*='plan-card']",
            "[class*='tier-card']",
            "[class*='package-card']",
            "[class*='subscription-card']",
        ],
        "content": [
            "[class*='blog-card']",
            "[class*='blog-post']",
            "[class*='article-card']",
            "[class*='article-post']",
            "[class*='post-card']",
            "[class*='news-card']",
            "[class*='blog-item']",
            "[class*='article-item']",
        ],
    }

    # Sections to exclude from service extraction
    EXCLUDE_SECTIONS: ClassVar[set[str]] = {
        "faq", "help", "support", "footer", "header",
        "nav", "menu", "sidebar", "modal", "popup",
    }

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        self._extract_services(soup, result, url)
        self._extract_pricing(soup, result, url)
        self._extract_content(soup, result, url)
        return result

    def _is_in_excluded_section(self, element: Tag) -> bool:
        """Check if element is inside a FAQ/help/nav section."""
        parent = element.parent
        while parent and isinstance(parent, Tag):
            classes = " ".join(parent.get("class", []))
            element_id = parent.get("id", "")
            combined = f"{classes} {element_id}".lower()
            for excluded in self.EXCLUDE_SECTIONS:
                if excluded in combined:
                    return True
            parent = parent.parent
        return False

    def _extract_services(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        seen_names: set[str] = {s.get("name") for s in result.services}
        for pattern in self.CSS_PATTERNS["service"]:
            for card in soup.select(pattern):
                if self._is_in_excluded_section(card):
                    continue
                name_el = card.select_one("h2, h3, h4, h5, .name, .title, .service-name")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not is_valid_service_name(name) or name in seen_names:
                    continue
                desc_el = card.select_one(
                    "p, .description, .desc, .summary, .service-description"
                )
                price_el = card.select_one(
                    "[class*='price'], [class*='amount'], [class*='cost']"
                )
                duration_el = card.select_one("[class*='duration'], [class*='time']")
                result.services.append(
                    {
                        "name": name,
                        "description": desc_el.get_text(strip=True) if desc_el else None,
                        "category": None,
                        "starting_price": parse_price(
                            price_el.get_text(strip=True) if price_el else None
                        ),
                        "currency": detect_currency_from_url(url),
                        "estimated_duration": (
                            duration_el.get_text(strip=True) if duration_el else None
                        ),
                    }
                )
                seen_names.add(name)

    def _extract_pricing(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        seen_names: set[str] = {p.get("service_name") for p in result.pricing}
        for pattern in self.CSS_PATTERNS["pricing"]:
            for card in soup.select(pattern):
                if self._is_in_excluded_section(card):
                    continue
                name_el = card.select_one(
                    "h2, h3, h4, h5, .name, .title, .plan-name, .tier-name"
                )
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not is_valid_service_name(name) or name in seen_names:
                    continue
                price_text = self._text(
                    card, "[class*='price'], [class*='amount'], [class*='cost']"
                )
                promo_text = self._text(
                    card, "[class*='promo'], [class*='sale'], [class*='discount']"
                )
                base_price = parse_price(price_text)
                promo_price = parse_price(promo_text)
                if not base_price:
                    continue
                discount = None
                if base_price and promo_price and base_price > 0:
                    discount = round((1 - promo_price / base_price) * 100, 1)
                result.pricing.append(
                    {
                        "service_name": name,
                        "category": None,
                        "base_price": base_price,
                        "promotional_price": promo_price,
                        "currency": detect_currency_from_url(url),
                        "discount": discount,
                        "subscription_plans": {},
                        "membership_pricing": None,
                    }
                )
                seen_names.add(name)

    def _extract_content(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        seen_titles: set[str] = {c.get("title") for c in result.content}
        for pattern in self.CSS_PATTERNS["content"]:
            for card in soup.select(pattern):
                if self._is_in_excluded_section(card):
                    continue
                title_el = card.select_one("h2, h3, h4, .title, .headline")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not is_valid_content_title(title) or title in seen_titles:
                    continue
                link_el = card.select_one("a[href]")
                link = str(link_el.get("href", "")) if link_el else None
                summary_el = card.select_one("p, .summary, .excerpt")
                date_el = card.select_one("time, [class*='date'], [class*='published']")
                result.content.append(
                    {
                        "title": title,
                        "author": None,
                        "publish_date": (
                            date_el.get("datetime") or date_el.get_text(strip=True)
                            if date_el
                            else None
                        ),
                        "url": urljoin(url, link) if link else None,
                        "summary": summary_el.get_text(strip=True) if summary_el else None,
                        "content_type": "article",
                    }
                )
                seen_titles.add(title)
