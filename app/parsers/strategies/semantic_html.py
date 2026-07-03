from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS, detect_currency, parse_price
from app.parsers.strategy import ParsedResult, ParsingStrategy


class SemanticHtmlStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "semantic_html"

    @property
    def weight(self) -> float:
        return 0.15

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        self._extract_from_header(soup, result, url)
        self._extract_from_nav(soup, result, url)
        self._extract_from_main(soup, result, url)
        self._extract_from_footer(soup, result, url)
        self._extract_from_articles(soup, result, url)
        self._extract_from_sections(soup, result, url)
        self._extract_emails(soup, result)
        self._extract_phones(soup, result)
        self._extract_social_links(soup, result, url)
        return result

    def _extract_from_header(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        header = soup.select_one("header")
        if not header:
            return
        if not result.company_name:
            h1 = header.select_one("h1")
            if h1:
                result.company_name = h1.get_text(strip=True)
        if not result.logo:
            img = header.select_one("img")
            if img:
                src = str(img.get("src", ""))
                if src:
                    result.logo = urljoin(url, src)

    def _extract_from_nav(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        nav = soup.select_one("nav")
        if not nav:
            return
        if not result.company_name:
            brand = nav.select_one("[class*='brand'], [class*='logo'], .company-name")
            if brand:
                result.company_name = brand.get_text(strip=True)
        for a_tag in nav.select("a[href]"):
            href = str(a_tag.get("href", ""))
            text = a_tag.get_text(strip=True).lower()
            if any(
                kw in text for kw in ["service", "services", "pricing", "about", "contact"]
            ) and (href.startswith("/") or href.startswith(".")):
                pass

    def _extract_from_main(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        main = soup.select_one("main")
        if not main:
            return
        self._extract_services_from_headings(main, result)
        self._extract_pricing_from_tables(main, result)

    def _extract_services_from_headings(self, container: Any, result: ParsedResult) -> None:
        service_keywords = ["service", "repair", "install", "maintenance", "plan", "cleaning"]
        headings = container.select("h2, h3, h4")
        for heading in headings:
            text = heading.get_text(strip=True)
            if any(kw in text.lower() for kw in service_keywords):
                desc_el = heading.find_next_sibling("p")
                result.services.append(
                    {
                        "name": text,
                        "description": desc_el.get_text(strip=True) if desc_el else None,
                        "category": None,
                        "starting_price": None,
                        "currency": "USD",
                        "estimated_duration": None,
                    }
                )

    def _extract_pricing_from_tables(self, container: Any, result: ParsedResult) -> None:
        for table in container.select("table"):
            rows = table.select("tr")
            if len(rows) < 2:
                continue
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.select("td")]
                if len(cells) >= 2:
                    result.pricing.append(
                        {
                            "service_name": cells[0],
                            "category": cells[2] if len(cells) > 2 else None,
                            "base_price": parse_price(cells[1]),
                            "promotional_price": None,
                            "currency": detect_currency(cells[1]),
                            "discount": None,
                            "subscription_plans": {},
                            "membership_pricing": None,
                        }
                    )

    def _extract_from_footer(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        footer = soup.select_one("footer")
        if not footer:
            return
        if not result.contact_email:
            email_link = footer.select_one("a[href^='mailto:']")
            if email_link:
                result.contact_email = str(email_link["href"]).replace("mailto:", "")
        if not result.contact_phone:
            phone_link = footer.select_one("a[href^='tel:']")
            if phone_link:
                result.contact_phone = str(phone_link["href"]).replace("tel:", "")

    def _extract_from_articles(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for article in soup.select("article"):
            title_el = article.select_one("h1, h2, h3, h4")
            title = title_el.get_text(strip=True) if title_el else None
            link_el = article.select_one("a[href]")
            link = str(link_el.get("href", "")) if link_el else None
            summary_el = article.select_one("p, .summary, .excerpt")
            summary = summary_el.get_text(strip=True) if summary_el else None
            author_el = article.select_one(".author, .byline, [data-author]")
            author = author_el.get_text(strip=True) if author_el else None
            if title:
                result.content.append(
                    {
                        "title": title,
                        "author": author,
                        "publish_date": None,
                        "url": urljoin(url, link) if link else None,
                        "summary": summary,
                        "content_type": "article",
                    }
                )

    def _extract_from_sections(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for section in soup.select("section"):
            heading = section.select_one("h2, h3")
            if not heading:
                continue
            text = heading.get_text(strip=True).lower()
            if any(kw in text for kw in ["service", "what we do", "our services"]):
                desc_el = section.select_one("p")
                if desc_el:
                    result.services.append(
                        {
                            "name": heading.get_text(strip=True),
                            "description": desc_el.get_text(strip=True),
                            "category": None,
                            "starting_price": None,
                            "currency": "USD",
                            "estimated_duration": None,
                        }
                    )

    def _extract_emails(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.contact_email:
            return
        email_link = soup.select_one("a[href^='mailto:']")
        if email_link:
            result.contact_email = str(email_link["href"]).replace("mailto:", "")

    def _extract_phones(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.contact_phone:
            return
        phone_link = soup.select_one("a[href^='tel:']")
        if phone_link:
            result.contact_phone = str(phone_link["href"]).replace("tel:", "")

    def _extract_social_links(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        for a_tag in soup.select("a[href]"):
            href = str(a_tag.get("href", ""))
            for domain, platform in SOCIAL_PLATFORM_DOMAINS.items():
                if domain in href and platform not in result.social_links:
                    result.social_links[platform] = urljoin(url, href)
