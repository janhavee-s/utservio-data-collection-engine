"""Intelligent Page Classification — classifies every page.

Classifies pages using multiple signals:
- URL path patterns
- Heading content
- Meta tags
- Structured data (JSON-LD, Schema.org)
- DOM context

Possible types:
Homepage, Service, Pricing, Blog, FAQ, Contact, About,
Legal, Career, Support, Unknown
"""

import re
from dataclasses import dataclass

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class PageType:
    HOMEPAGE = "homepage"
    SERVICE = "service"
    PRICING = "pricing"
    BLOG = "blog"
    FAQ = "faq"
    CONTACT = "contact"
    ABOUT = "about"
    LEGAL = "legal"
    CAREER = "career"
    SUPPORT = "support"
    TESTIMONIAL = "testimonial"
    UNKNOWN = "unknown"


URL_PATTERNS: dict[str, list[tuple[str, float]]] = {
    PageType.HOMEPAGE: [
        (r"^https?://[^/]+/?$", 0.9),
        (r"/index\.(html|php|asp)$", 0.8),
    ],
    PageType.SERVICE: [
        (r"/service", 0.9),
        (r"/product", 0.85),
        (r"/feature", 0.7),
        (r"/solution", 0.7),
        (r"/offering", 0.6),
    ],
    PageType.PRICING: [
        (r"/pric", 0.95),
        (r"/cost", 0.85),
        (r"/plan", 0.7),
        (r"/subscription", 0.7),
        (r"/tier", 0.6),
        (r"/rate", 0.5),
    ],
    PageType.BLOG: [
        (r"/blog", 0.95),
        (r"/article", 0.9),
        (r"/news", 0.8),
        (r"/post", 0.7),
        (r"/resource", 0.6),
        (r"/press", 0.6),
    ],
    PageType.FAQ: [
        (r"/faq", 0.95),
        (r"/question", 0.7),
        (r"/answer", 0.6),
    ],
    PageType.CONTACT: [
        (r"/contact", 0.95),
        (r"/reach", 0.6),
        (r"/get-in-touch", 0.8),
    ],
    PageType.ABOUT: [
        (r"/about", 0.95),
        (r"/company", 0.7),
        (r"/team", 0.7),
        (r"/story", 0.6),
        (r"/mission", 0.6),
        (r"/values", 0.5),
    ],
    PageType.LEGAL: [
        (r"/privacy", 0.9),
        (r"/terms", 0.9),
        (r"/legal", 0.9),
        (r"/policy", 0.7),
        (r"/cookie", 0.8),
        (r"/gdpr", 0.8),
    ],
    PageType.CAREER: [
        (r"/career", 0.95),
        (r"/job", 0.8),
        (r"/hiring", 0.8),
        (r"/recruit", 0.7),
        (r"/work-with", 0.6),
    ],
    PageType.SUPPORT: [
        (r"/support", 0.9),
        (r"/help", 0.8),
        (r"/documentation", 0.7),
        (r"/docs", 0.7),
        (r"/guide", 0.6),
    ],
    PageType.TESTIMONIAL: [
        (r"/testimonial", 0.95),
        (r"/review", 0.8),
        (r"/case-study", 0.8),
        (r"/success-story", 0.7),
    ],
}

HEADING_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    PageType.SERVICE: [
        (r"our\s+service", 0.9),
        (r"what\s+we\s+do", 0.85),
        (r"our\s+product", 0.85),
        (r"service\s+offering", 0.8),
    ],
    PageType.PRICING: [
        (r"pricing", 0.95),
        (r"our\s+plan", 0.85),
        (r"choose\s+your\s+plan", 0.9),
        (r"subscription\s+plan", 0.85),
    ],
    PageType.BLOG: [
        (r"latest\s+post", 0.9),
        (r"blog\s+post", 0.95),
        (r"article", 0.7),
        (r"news", 0.6),
    ],
    PageType.FAQ: [
        (r"frequently\s+asked", 0.95),
        (r"question", 0.7),
    ],
    PageType.CONTACT: [
        (r"contact\s+us", 0.95),
        (r"get\s+in\s+touch", 0.9),
        (r"reach\s+us", 0.85),
    ],
    PageType.ABOUT: [
        (r"about\s+us", 0.95),
        (r"our\s+story", 0.9),
        (r"our\s+team", 0.85),
        (r"our\s+mission", 0.85),
    ],
    PageType.LEGAL: [
        (r"privacy\s+policy", 0.95),
        (r"terms\s+of\s+service", 0.95),
        (r"terms\s+and\s+conditions", 0.95),
    ],
    PageType.CAREER: [
        (r"join\s+our\s+team", 0.9),
        (r"career", 0.9),
        (r"job\s+openings", 0.9),
    ],
    PageType.SUPPORT: [
        (r"help\s+center", 0.9),
        (r"support\s+center", 0.9),
        (r"documentation", 0.8),
    ],
}

SCHEMA_ORG_TYPES: dict[str, str] = {
    "Product": PageType.SERVICE,
    "Service": PageType.SERVICE,
    "Offer": PageType.PRICING,
    "PriceSpecification": PageType.PRICING,
    "BlogPosting": PageType.BLOG,
    "Blog": PageType.BLOG,
    "Article": PageType.BLOG,
    "FAQPage": PageType.FAQ,
    "ContactPage": PageType.CONTACT,
    "AboutPage": PageType.ABOUT,
    "WebPage": PageType.UNKNOWN,
    "Organization": PageType.ABOUT,
    "LocalBusiness": PageType.ABOUT,
    "JobPosting": PageType.CAREER,
}


@dataclass
class ClassificationResult:
    """Result of page classification."""

    page_type: str
    confidence: float
    signals_used: list[str]


class PageClassifier:
    """Classifies pages using URL, heading, metadata, and structured data signals.

    Combines multiple classification signals with weighted scoring.
    Never relies on a single signal alone.
    """

    def classify(self, html: str, url: str) -> ClassificationResult:
        """Classify a page using all available signals."""
        scores: dict[str, float] = {}
        signals: list[str] = []

        url_score = self._classify_by_url(url)
        if url_score:
            best_type = max(url_score, key=url_score.get)  # type: ignore[arg-type]
            scores[best_type] = url_score[best_type]
            signals.append(f"url:{best_type}")

        soup = BeautifulSoup(html, "html.parser")

        heading_score = self._classify_by_headings(soup)
        if heading_score:
            best_type = max(heading_score, key=heading_score.get)  # type: ignore[arg-type]
            scores[best_type] = scores.get(best_type, 0) + heading_score[best_type]
            signals.append(f"heading:{best_type}")

        schema_score = self._classify_by_schema(soup)
        if schema_score:
            best_type = max(schema_score, key=schema_score.get)  # type: ignore[arg-type]
            scores[best_type] = scores.get(best_type, 0) + schema_score[best_type]
            signals.append(f"schema:{best_type}")

        meta_score = self._classify_by_meta(soup)
        if meta_score:
            best_type = max(meta_score, key=meta_score.get)  # type: ignore[arg-type]
            scores[best_type] = scores.get(best_type, 0) + meta_score[best_type]
            signals.append(f"meta:{best_type}")

        if not scores:
            return ClassificationResult(
                page_type=PageType.UNKNOWN,
                confidence=0.1,
                signals_used=["no_signals"],
            )

        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        confidence = min(0.95, scores[best_type] / max(len(signals), 1))

        return ClassificationResult(
            page_type=best_type,
            confidence=confidence,
            signals_used=signals,
        )

    def _classify_by_url(self, url: str) -> dict[str, float]:
        """Classify by URL path patterns."""
        scores: dict[str, float] = {}
        url_lower = url.lower()

        for page_type, patterns in URL_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, url_lower):
                    scores[page_type] = max(scores.get(page_type, 0), weight)
                    break

        return scores

    def _classify_by_headings(self, soup: BeautifulSoup) -> dict[str, float]:
        """Classify by heading content keywords."""
        scores: dict[str, float] = {}

        for tag_name in ["h1", "h2", "h3"]:
            headings = soup.find_all(tag_name)
            for heading in headings:
                text = heading.get_text(strip=True).lower()
                for page_type, patterns in HEADING_KEYWORDS.items():
                    for pattern, weight in patterns:
                        if re.search(pattern, text):
                            scores[page_type] = max(scores.get(page_type, 0), weight)

        return scores

    def _classify_by_schema(self, soup: BeautifulSoup) -> dict[str, float]:
        """Classify by structured data types."""
        scores: dict[str, float] = {}

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    item_type = item.get("@type", "")
                    if item_type in SCHEMA_ORG_TYPES:
                        page_type = SCHEMA_ORG_TYPES[item_type]
                        scores[page_type] = max(scores.get(page_type, 0), 0.8)
            except (json.JSONDecodeError, TypeError):
                continue

        return scores

    def _classify_by_meta(self, soup: BeautifulSoup) -> dict[str, float]:
        """Classify by meta tags."""
        scores: dict[str, float] = {}

        title = soup.find("title")
        if title and title.string:
            title_text = str(title.string).lower()
            for page_type, patterns in URL_PATTERNS.items():
                for pattern, weight in patterns:
                    clean_pattern = pattern.replace("^https?://[^/]+/?$", "").replace("/?", "")
                    if clean_pattern and re.search(clean_pattern.replace("\\", ""), title_text):
                        scores[page_type] = max(scores.get(page_type, 0), weight * 0.8)

        og_type = soup.find("meta", property="og:type")
        if og_type:
            content = str(og_type.get("content", "")).lower()
            if "article" in content:
                scores[PageType.BLOG] = max(scores.get(PageType.BLOG, 0), 0.7)
            elif "website" in content:
                scores[PageType.HOMEPAGE] = max(scores.get(PageType.HOMEPAGE, 0), 0.5)

        return scores
