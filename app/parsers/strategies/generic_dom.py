import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS, detect_currency, parse_price
from app.parsers.strategy import ParsedResult, ParsingStrategy


class GenericDomHeuristicStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "generic_dom_heuristic"

    @property
    def weight(self) -> float:
        return 0.10

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        self._analyze_heading_hierarchy(soup, result)
        self._analyze_link_density(soup, result, url)
        self._analyze_price_elements(soup, result)
        self._analyze_contact_elements(soup, result)
        return result

    def _analyze_heading_hierarchy(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        h1_tags = soup.select("h1")
        if h1_tags and not result.company_name:
            result.company_name = h1_tags[0].get_text(strip=True)

    def _analyze_link_density(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for a_tag in soup.select("a[href]"):
            href = str(a_tag.get("href", ""))
            for domain, platform in SOCIAL_PLATFORM_DOMAINS.items():
                if domain in href and platform not in result.social_links:
                    result.social_links[platform] = urljoin(url, href)

    def _analyze_price_elements(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.pricing:
            return
        price_pattern = re.compile(r"\$\d+(?:\.\d{2})?|\d+(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)")
        for element in soup.select(
            "[class*='price'], [class*='cost'], [class*='amount'], [data-price]"
        ):
            text = element.get_text(strip=True)
            if price_pattern.search(text):
                price = parse_price(text)
                if price is not None:
                    parent = element.find_parent(["div", "section", "article", "li"])
                    service_name = "Detected Service"
                    if parent:
                        heading = parent.select_one("h2, h3, h4, h5")
                        if heading:
                            service_name = heading.get_text(strip=True)
                    result.pricing.append(
                        {
                            "service_name": service_name,
                            "category": None,
                            "base_price": price,
                            "promotional_price": None,
                            "currency": detect_currency(text),
                            "discount": None,
                            "subscription_plans": {},
                            "membership_pricing": None,
                        }
                    )

    def _analyze_contact_elements(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if not result.contact_email:
            email_link = soup.select_one("a[href^='mailto:']")
            if email_link:
                result.contact_email = str(email_link["href"]).replace("mailto:", "")
        if not result.contact_phone:
            phone_link = soup.select_one("a[href^='tel:']")
            if phone_link:
                result.contact_phone = str(phone_link["href"]).replace("tel:", "")
