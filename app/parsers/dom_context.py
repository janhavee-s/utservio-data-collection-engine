"""DOM Context Parser — extracts information from DOM relationships.

Instead of relying on CSS selectors (which break across sites),
this parser uses DOM context:
- Heading → Nearest paragraph → Nearest list → Nearest button
- Heading → Nearest table → Nearest price → Nearest image
- Section context → Nearest metadata

Extracts information from context rather than class names.
Never depends on website-specific selectors.
"""

import contextlib
import re
from dataclasses import dataclass, field
from typing import Any

import structlog
from bs4 import BeautifulSoup, Tag

logger = structlog.get_logger(__name__)

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK_TAGS = {"div", "section", "article", "main", "aside", "nav", "header", "footer"}
TEXT_TAGS = {"p", "span", "li", "td", "th", "dd", "dt", "blockquote"}
INTERACTIVE_TAGS = {"button", "a", "input", "select", "textarea"}
LIST_TAGS = {"ul", "ol", "dl"}


@dataclass
class DOMContext:
    """Context extracted from a DOM region."""

    heading: str = ""
    heading_tag: str = ""
    paragraph: str = ""
    list_items: list[str] = field(default_factory=list)
    button_text: str = ""
    table_data: list[list[str]] = field(default_factory=list)
    price_text: str = ""
    image_url: str = ""
    image_alt: str = ""
    link_url: str = ""
    link_text: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    element_type: str = ""


@dataclass
class ExtractedService:
    """A service extracted from DOM context."""

    name: str = ""
    description: str = ""
    category: str = ""
    price: float | None = None
    duration: str = ""
    url: str = ""


@dataclass
class ExtractedPricing:
    """Pricing extracted from DOM context."""

    service_name: str = ""
    base_price: float | None = None
    promotional_price: float | None = None
    currency: str = "USD"
    category: str = ""
    period: str = ""


@dataclass
class ExtractedArticle:
    """An article extracted from DOM context."""

    title: str = ""
    summary: str = ""
    url: str = ""
    author: str = ""
    date: str = ""
    category: str = ""


class DOMContextParser:
    """Extracts structured data from DOM context relationships.

    Uses proximity and DOM hierarchy rather than CSS class names.
    Works across different website designs without site-specific selectors.
    """

    PRICE_PATTERN = re.compile(
        r"[\$€£¥₹]\s*[\d,]+\.?\d*|"
        r"[\d,]+\.?\d*\s*(?:USD|EUR|GBP|INR|per\s+month|/mo|/yr|/year|/day)",
        re.IGNORECASE,
    )

    def parse(self, html: str, url: str) -> dict[str, Any]:
        """Parse HTML and extract structured data from DOM context."""
        soup = BeautifulSoup(html, "html.parser")

        return {
            "services": self._extract_services(soup, url),
            "pricing": self._extract_pricing(soup, url),
            "articles": self._extract_articles(soup, url),
            "contact": self._extract_contact(soup),
            "social_profiles": self._extract_social_links(soup, url),
            "company_name": self._extract_company_name(soup),
            "description": self._extract_description(soup),
        }

    def _find_nearest(
        self,
        element: Tag,
        tag_filter: set[str] | None = None,
        max_distance: int = 5,
    ) -> Tag | None:
        """Find the nearest sibling or cousin matching the tag filter."""
        if tag_filter is None:
            tag_filter = TEXT_TAGS | BLOCK_TAGS

        current: Tag | None = element
        for _ in range(max_distance):
            if current is None:
                break
            next_sibling = current.find_next_sibling()
            if next_sibling and isinstance(next_sibling, Tag):
                if next_sibling.name in tag_filter:
                    return next_sibling
                child = next_sibling.find(True)
                if child and child.name in tag_filter:
                    return child
            current = next_sibling

        current = element
        for _ in range(max_distance):
            if current is None:
                break
            prev_sibling = current.find_previous_sibling()
            if prev_sibling and isinstance(prev_sibling, Tag):
                if prev_sibling.name in tag_filter:
                    return prev_sibling
                children = prev_sibling.find_all(True)
                for child in reversed(children):
                    if child.name in tag_filter:
                        return child
            current = prev_sibling

        return None

    def _extract_text_near(self, element: Tag, max_distance: int = 3) -> str:
        """Extract text from the nearest text-bearing element."""
        nearest = self._find_nearest(element, TEXT_TAGS, max_distance)
        if nearest:
            return str(nearest.get_text(strip=True))
        return ""

    def _extract_context(self, heading: Tag) -> DOMContext:
        """Extract full context from a heading element."""
        ctx = DOMContext(
            heading=heading.get_text(strip=True),
            heading_tag=heading.name,
        )

        para = self._find_nearest(heading, {"p"}, 3)
        if para:
            ctx.paragraph = para.get_text(strip=True)

        lst = self._find_nearest(heading, LIST_TAGS, 3)
        if lst:
            ctx.list_items = [
                li.get_text(strip=True) for li in lst.find_all("li") if li.get_text(strip=True)
            ]

        btn = self._find_nearest(heading, {"button"}, 3)
        if btn:
            ctx.button_text = btn.get_text(strip=True)

        tbl = self._find_nearest(heading, {"table"}, 3)
        if tbl:
            for row in tbl.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if cells:
                    ctx.table_data.append(cells)

        img = self._find_nearest(heading, {"img"}, 3)
        if img:
            ctx.image_url = str(img.get("src", ""))
            ctx.image_alt = str(img.get("alt", ""))

        link = self._find_nearest(heading, {"a"}, 3)
        if link:
            ctx.link_url = str(link.get("href", ""))
            ctx.link_text = link.get_text(strip=True)

        price_text = self._extract_text_near(heading, 3)
        if self.PRICE_PATTERN.search(price_text):
            ctx.price_text = price_text

        return ctx

    def _extract_services(self, soup: BeautifulSoup, url: str) -> list[dict[str, Any]]:
        """Extract services using heading→context proximity."""
        services: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        service_headings = [
            h
            for h in soup.find_all(re.compile(r"^h[2-4]$"))
            if h.string
            and re.search(
                r"service|our\s+service|what\s+we\s+do|solution|offering",
                str(h.string),
                re.IGNORECASE,
            )
        ]

        if not service_headings:
            service_headings = soup.find_all(
                re.compile(r"^h[2-4]$"),
            )

        for heading in service_headings:
            ctx = self._extract_context(heading)
            if not ctx.heading or ctx.heading in seen_names:
                continue

            name = ctx.heading
            if len(name) > 100:
                continue

            description = ctx.paragraph
            if ctx.list_items:
                description = " | ".join(ctx.list_items[:5])

            price = None
            if ctx.price_text:
                price_match = self.PRICE_PATTERN.search(ctx.price_text)
                if price_match:
                    price_str = re.sub(r"[^\d.]", "", price_match.group())
                    with contextlib.suppress(ValueError):
                        price = float(price_str)

            services.append(
                {
                    "name": name,
                    "description": description[:500] if description else "",
                    "starting_price": price,
                    "category": self._categorize_content(name),
                    "url": url,
                }
            )
            seen_names.add(name)

        return services[:50]

    def _extract_pricing(self, soup: BeautifulSoup, url: str) -> list[dict[str, Any]]:
        """Extract pricing using heading→price proximity."""
        pricing: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        pricing_headings = [
            h
            for h in soup.find_all(re.compile(r"^h[2-4]$"))
            if h.string
            and re.search(
                r"pric|cost|plan|subscription|tier",
                str(h.string),
                re.IGNORECASE,
            )
        ]

        if not pricing_headings:
            price_elements = soup.find_all(string=self.PRICE_PATTERN)
            for price_el in price_elements:
                if not isinstance(price_el, Tag):
                    continue
                parent = price_el.find_parent()
                if parent:
                    heading = parent.find_previous(re.compile(r"^h[2-6]$"))
                    if heading:
                        pricing_headings.append(heading)

        for heading in pricing_headings:
            ctx = self._extract_context(heading)
            if not ctx.heading or ctx.heading in seen_names:
                continue

            price = None
            if ctx.price_text:
                price_match = self.PRICE_PATTERN.search(ctx.price_text)
                if price_match:
                    price_str = re.sub(r"[^\d.]", "", price_match.group())
                    with contextlib.suppress(ValueError):
                        price = float(price_str)

            pricing.append(
                {
                    "service_name": ctx.heading,
                    "base_price": price,
                    "category": self._categorize_content(ctx.heading),
                    "url": url,
                }
            )
            seen_names.add(ctx.heading)

        return pricing[:50]

    def _extract_articles(self, soup: BeautifulSoup, url: str) -> list[dict[str, Any]]:
        """Extract articles using article tags and heading→paragraph proximity."""
        articles: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        article_tags = soup.find_all("article")
        for article in article_tags:
            heading = article.find(re.compile(r"^h[1-6]$"))
            if not heading:
                continue
            title = heading.get_text(strip=True)
            if title in seen_titles or not title:
                continue

            summary = ""
            p_tag = article.find("p")
            if p_tag:
                summary = p_tag.get_text(strip=True)

            link = article.find("a", href=True)
            link_url = ""
            if link:
                from urllib.parse import urljoin as _urljoin

                link_url = _urljoin(url, str(link["href"]))

            date_el = article.find("time")
            date_str = ""
            if date_el:
                raw = date_el.get("datetime") or date_el.get_text(strip=True)
                date_str = str(raw) if raw else ""

            articles.append(
                {
                    "title": title,
                    "summary": summary[:500],
                    "url": link_url or url,
                    "date": date_str,
                }
            )
            seen_titles.add(title)

        if not articles:
            headings = soup.find_all(re.compile(r"^h[2-4]$"))
            for heading in headings:
                ctx = self._extract_context(heading)
                if not ctx.heading or ctx.heading in seen_titles:
                    continue
                if len(ctx.heading) < 5 or len(ctx.heading) > 200:
                    continue

                articles.append(
                    {
                        "title": ctx.heading,
                        "summary": ctx.paragraph[:500] if ctx.paragraph else "",
                        "url": url,
                    }
                )
                seen_titles.add(ctx.heading)

        return articles[:50]

    def _extract_contact(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract contact information from DOM context."""
        contact: dict[str, str] = {}

        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        phone_pattern = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")

        text = soup.get_text()
        emails = email_pattern.findall(text)
        if emails:
            contact["email"] = emails[0]

        phones = phone_pattern.findall(text)
        if phones:
            cleaned = re.sub(r"[^\d+]", "", phones[0])
            if len(cleaned) >= 7:
                contact["phone"] = phones[0].strip()

        mailto_links = soup.find_all("a", href=re.compile(r"mailto:"))
        if mailto_links:
            href = str(mailto_links[0].get("href", ""))
            contact["email"] = href.replace("mailto:", "").split("?")[0]

        tel_links = soup.find_all("a", href=re.compile(r"tel:"))
        if tel_links:
            href = str(tel_links[0].get("href", ""))
            contact["phone"] = href.replace("tel:", "")

        return contact

    def _extract_social_links(self, soup: BeautifulSoup, url: str) -> list[dict[str, str]]:
        """Extract social media profiles."""
        profiles: list[dict[str, str]] = []
        seen_platforms: set[str] = set()

        social_domains = {
            "linkedin.com": "linkedin",
            "facebook.com": "facebook",
            "twitter.com": "twitter",
            "x.com": "twitter",
            "instagram.com": "instagram",
            "youtube.com": "youtube",
            "pinterest.com": "pinterest",
            "threads.net": "threads",
        }

        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag["href"])
            for domain, platform in social_domains.items():
                if domain in href.lower() and platform not in seen_platforms:
                    profiles.append(
                        {
                            "platform": platform,
                            "profile_url": href,
                            "username": "",
                        }
                    )
                    seen_platforms.add(platform)
                    break

        return profiles

    def _extract_company_name(self, soup: BeautifulSoup) -> str | None:
        """Extract company name from meta tags or first h1."""
        og_site = soup.find("meta", property="og:site_name")
        if og_site:
            content = og_site.get("content")
            if content:
                return str(content)

        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = str(title_tag.string).strip()
            parts = re.split(r"[\|---]", title)
            if parts:
                return parts[0].strip()

        h1 = soup.find("h1")
        if h1:
            return str(h1.get_text(strip=True))

        return None

    def _extract_description(self, soup: BeautifulSoup) -> str | None:
        """Extract page description from meta tags."""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content")
            if content:
                return str(content)

        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            content = og_desc.get("content")
            if content:
                return str(content)

        return None

    def _categorize_content(self, text: str) -> str:
        """Categorize content based on keywords."""
        text_lower = text.lower()

        if any(w in text_lower for w in ("blog", "article", "news", "post", "press")):
            return "content"
        if any(w in text_lower for w in ("pric", "cost", "plan", "subscription", "tier")):
            return "pricing"
        if any(w in text_lower for w in ("service", "product", "feature", "solution")):
            return "services"
        if any(w in text_lower for w in ("about", "company", "team", "story")):
            return "company"
        if any(w in text_lower for w in ("contact", "support", "help")):
            return "contact"
        if any(w in text_lower for w in ("faq", "question", "answer")):
            return "faq"
        if any(w in text_lower for w in ("review", "testimonial", "case")):
            return "social_proof"
        return "general"
