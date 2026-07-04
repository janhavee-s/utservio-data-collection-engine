import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.parsers.strategies.shared import (
    SOCIAL_PLATFORM_DOMAINS,
    detect_currency_from_url,
    is_valid_content_title,
    is_valid_service_name,
    parse_price,
)
from app.parsers.strategy import ParsedResult, ParsingStrategy

# URL patterns that indicate a service page
_SERVICE_URL_PATTERNS = re.compile(
    r"(?:/service|cleaning|repair|salon|beauty|ac-service|plumb|electric|pest|paint|cook|chef|"
    r"massage|spa|groom|appliance|wash|laundry|shifting|mover|home-|interior|"
    r"water-purifier|smart-lock|laptop-repair|fridge|washing-machine|microwave|stove)",
    re.I,
)

# Words in link text that indicate a service
_SERVICE_TEXT_PATTERNS = re.compile(
    r"(?:cleaning|repair|service|salon|beauty|ac|plumb|electric|pest|paint|cook|chef|"
    r"massage|spa|groom|appliance|wash|laundry|mover|shifting|interior|purifier|"
    r"haircut|waxing|facial|manicure|pedicure|cleanup|fixing|installation|check-up)",
    re.I,
)


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
        self._extract_from_main(soup, result, url)
        self._extract_from_footer(soup, result, url)
        self._extract_from_articles(soup, result, url)
        self._extract_from_sections(soup, result, url)
        self._extract_services_from_links(soup, result, url)
        self._extract_prices_from_cards(soup, result, url)
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

    def _extract_from_main(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        main = soup.select_one("main, [role='main'], #main, .main-content, #content")
        if not main:
            return
        self._extract_services_from_headings(main, result, url)
        self._extract_pricing_from_tables(main, result, url)

    def _extract_services_from_headings(
        self, container: Any, result: ParsedResult, url: str
    ) -> None:
        seen_names: set[str] = {s.get("name") for s in result.services}
        headings = container.select("h2, h3, h4")
        for heading in headings:
            text = heading.get_text(strip=True)
            if not is_valid_service_name(text) or text in seen_names:
                continue
            # Check if this heading is in a FAQ section
            parent = heading.parent
            in_faq = False
            while parent and isinstance(parent, Tag):
                classes = " ".join(parent.get("class", []))
                element_id = parent.get("id", "")
                combined = f"{classes} {element_id}".lower()
                if any(kw in combined for kw in ("faq", "help", "support", "accordion")):
                    in_faq = True
                    break
                parent = parent.parent
            if in_faq:
                continue
            desc_el = heading.find_next_sibling("p")
            result.services.append(
                {
                    "name": text,
                    "description": desc_el.get_text(strip=True) if desc_el else None,
                    "category": None,
                    "starting_price": None,
                    "currency": detect_currency_from_url(url),
                    "estimated_duration": None,
                }
            )
            seen_names.add(text)

    def _extract_pricing_from_tables(
        self, container: Any, result: ParsedResult, url: str
    ) -> None:
        for table in container.select("table"):
            rows = table.select("tr")
            if len(rows) < 2:
                continue
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.select("td")]
                if len(cells) >= 2:
                    service_name = cells[0]
                    if not is_valid_service_name(service_name):
                        continue
                    base_price = parse_price(cells[1])
                    if not base_price:
                        continue
                    result.pricing.append(
                        {
                            "service_name": service_name,
                            "category": cells[2] if len(cells) > 2 else None,
                            "base_price": base_price,
                            "promotional_price": None,
                            "currency": detect_currency_from_url(url),
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
        seen_titles: set[str] = {c.get("title") for c in result.content}
        for article in soup.select("article"):
            title_el = article.select_one("h1, h2, h3, h4")
            title = title_el.get_text(strip=True) if title_el else None
            if not is_valid_content_title(title) or title in seen_titles:
                continue
            link_el = article.select_one("a[href]")
            link = str(link_el.get("href", "")) if link_el else None
            summary_el = article.select_one("p, .summary, .excerpt")
            summary = summary_el.get_text(strip=True) if summary_el else None
            author_el = article.select_one(".author, .byline, [data-author]")
            author = author_el.get_text(strip=True) if author_el else None
            date_el = article.select_one("time, [class*='date']")
            publish_date = None
            if date_el:
                publish_date = date_el.get("datetime") or date_el.get_text(strip=True)
            result.content.append(
                {
                    "title": title,
                    "author": author,
                    "publish_date": publish_date,
                    "url": urljoin(url, link) if link else None,
                    "summary": summary,
                    "content_type": "article",
                }
            )
            seen_titles.add(title)

    def _extract_from_sections(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        seen_names: set[str] = {s.get("name") for s in result.services}
        for section in soup.select("section"):
            heading = section.select_one("h2, h3")
            if not heading:
                continue
            text = heading.get_text(strip=True)
            if not is_valid_service_name(text) or text in seen_names:
                continue
            section_text = heading.get_text(strip=True).lower()
            if any(kw in section_text for kw in ["service", "what we do", "our services"]):
                desc_el = section.select_one("p")
                if desc_el:
                    result.services.append(
                        {
                            "name": text,
                            "description": desc_el.get_text(strip=True),
                            "category": None,
                            "starting_price": None,
                            "currency": detect_currency_from_url(url),
                            "estimated_duration": None,
                        }
                    )
                    seen_names.add(text)

    def _extract_services_from_links(
        self, soup: BeautifulSoup, result: ParsedResult, url: str
    ) -> None:
        """Extract real services from links that point to service pages."""
        seen_names: set[str] = {s.get("name") for s in result.services}
        seen_urls: set[str] = set()

        # Skip nav, header, footer
        skip_containers = set()
        for selector in ("nav", "header", "footer", "[role='navigation']"):
            for el in soup.select(selector):
                skip_containers.add(id(el))

        for a_tag in soup.select("a[href]"):
            # Skip if inside nav/header/footer
            parent = a_tag.parent
            in_skip = False
            while parent and isinstance(parent, Tag):
                if id(parent) in skip_containers:
                    in_skip = True
                    break
                parent = parent.parent
            if in_skip:
                continue

            href = str(a_tag.get("href", ""))
            # Get text from link, or from img alt, or from title attribute
            text = a_tag.get_text(strip=True)
            if not text:
                img = a_tag.select_one("img")
                if img:
                    text = str(img.get("alt", "")).strip()
            if not text:
                text = str(a_tag.get("title", "")).strip()

            if not text or not href or len(text) < 3 or len(text) > 100:
                continue
            if not _SERVICE_URL_PATTERNS.search(href):
                continue
            if not _SERVICE_TEXT_PATTERNS.search(text):
                continue
            if text in seen_names or href in seen_urls:
                continue
            if not is_valid_service_name(text):
                continue

            # Look for a nearby price
            nearby_price = None
            price_el = a_tag.find_next_sibling(
                "[class*='price'], [class*='amount'], [class*='cost']"
            )
            if price_el:
                nearby_price = parse_price(price_el.get_text(strip=True))

            result.services.append(
                {
                    "name": text,
                    "description": None,
                    "category": None,
                    "starting_price": nearby_price,
                    "currency": detect_currency_from_url(url),
                    "estimated_duration": None,
                }
            )
            seen_names.add(text)
            seen_urls.add(href)

    def _extract_prices_from_cards(
        self, soup: BeautifulSoup, result: ParsedResult, url: str
    ) -> None:
        """Extract service+price pairs from card containers (e.g., React Native CSS-in-JS)."""
        price_re = re.compile(r"₹\s*[\d,]+")
        seen_services: set[str] = {s.get("name") for s in result.services}
        seen_pricing: set[str] = {p.get("service_name") for p in result.pricing}
        currency = detect_currency_from_url(url)

        for price_el in soup.find_all(string=price_re):
            parent = price_el.parent
            if not parent or not isinstance(parent, Tag):
                continue

            # Walk up to find card container that has a service link
            card = parent
            for _ in range(10):
                if card.parent is None:
                    break
                card = card.parent
                if not isinstance(card, Tag):
                    break
                # Check if this level has a service link
                links = card.find_all("a", href=_SERVICE_URL_PATTERNS, limit=1)
                if links:
                    break

            if not isinstance(card, Tag):
                continue

            # Find service link in this card
            link = card.find("a", href=_SERVICE_URL_PATTERNS)
            if not link:
                continue

            # Get service name from link text or img alt
            service_name = link.get_text(strip=True)
            if not service_name:
                img = link.select_one("img")
                if img:
                    service_name = str(img.get("alt", "")).strip()
            if not service_name or len(service_name) < 3 or len(service_name) > 100:
                continue
            if not is_valid_service_name(service_name):
                continue

            # Extract price from the card text
            card_text = card.get_text(" ", strip=True)
            price_match = price_re.search(card_text)
            if not price_match:
                continue
            price_value = parse_price(price_match.group())
            if not price_value or price_value <= 0:
                continue

            # Add service if not already seen
            if service_name not in seen_services:
                result.services.append(
                    {
                        "name": service_name,
                        "description": None,
                        "category": None,
                        "starting_price": price_value,
                        "currency": currency,
                        "estimated_duration": None,
                    }
                )
                seen_services.add(service_name)
            else:
                # Backfill price if service was added without one
                for svc in result.services:
                    if svc["name"] == service_name and not svc.get("starting_price"):
                        svc["starting_price"] = price_value

            # Add pricing if not already seen
            if service_name not in seen_pricing:
                result.pricing.append(
                    {
                        "service_name": service_name,
                        "category": None,
                        "base_price": price_value,
                        "promotional_price": None,
                        "currency": currency,
                        "discount": None,
                        "subscription_plans": {},
                        "membership_pricing": None,
                    }
                )
                seen_pricing.add(service_name)

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
