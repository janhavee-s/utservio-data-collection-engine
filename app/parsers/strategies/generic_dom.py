from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS
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

    def _analyze_contact_elements(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if not result.contact_email:
            email_link = soup.select_one("a[href^='mailto:']")
            if email_link:
                result.contact_email = str(email_link["href"]).replace("mailto:", "")
        if not result.contact_phone:
            phone_link = soup.select_one("a[href^='tel:']")
            if phone_link:
                result.contact_phone = str(phone_link["href"]).replace("tel:", "")
