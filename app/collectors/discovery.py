import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.configuration.settings import get_settings
from app.utilities.url_normalizer import normalize_url

logger = structlog.get_logger(__name__)


@dataclass
class DiscoveredURL:
    """A discovered URL with metadata for ranking."""

    url: str
    source: str  # "nav", "footer", "sitemap", "robots", "internal_link", "meta"
    depth: int = 0
    context: str = ""  # anchor text or surrounding text


class DiscoveryEngine:
    """Discovers pages on a website using multiple strategies.

    Strategies (in priority order):
    1. robots.txt — find sitemaps and allowed paths
    2. sitemap.xml — exhaustive page list
    3. Navigation links — primary site structure
    4. Footer links — secondary pages (legal, contact, etc.)
    5. Internal links — all same-domain links
    6. Meta links — canonical, alternate
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings().discovery
        self._owned_client = client is None
        self._client = client

    async def discover(self, base_url: str) -> list[DiscoveredURL]:
        """Run full discovery pipeline and return ranked URLs."""
        all_urls: list[DiscoveredURL] = []

        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc.lower()

        needs_client = self._client is None or self._client.is_closed
        if needs_client:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30),
                headers={"User-Agent": get_settings().collector.user_agent},
                follow_redirects=True,
                verify=True,
            )
            self._owned_client = True

        assert self._client is not None

        try:
            if self._settings.fetch_robots_txt:
                robots_urls = await self._fetch_robots_txt(self._client, base_url)
                all_urls.extend(robots_urls)

            if self._settings.fetch_sitemap:
                sitemap_urls = await self._fetch_sitemaps(self._client, base_url)
                all_urls.extend(sitemap_urls)

            homepage_urls = await self._fetch_and_parse_page(self._client, base_url, "homepage")
            all_urls.extend(homepage_urls)

            if self._settings.same_domain_only:
                all_urls = [u for u in all_urls if self._is_same_domain(u.url, domain)]

            all_urls = self._deduplicate(all_urls)
            all_urls = self._rank(all_urls, domain)

            max_pages = self._settings.max_pages_per_competitor
            if len(all_urls) > max_pages:
                logger.info(
                    "discovery_truncated",
                    total=len(all_urls),
                    kept=max_pages,
                    url=base_url,
                )
                all_urls = all_urls[:max_pages]

            logger.info(
                "discovery_complete",
                url=base_url,
                total_urls=len(all_urls),
                sources=self._count_by_source(all_urls),
            )

        finally:
            if self._owned_client and self._client and not self._client.is_closed:
                await self._client.aclose()

        return all_urls

    async def _fetch_robots_txt(
        self, client: httpx.AsyncClient, base_url: str
    ) -> list[DiscoveredURL]:
        """Fetch robots.txt and extract sitemap URLs."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        urls: list[DiscoveredURL] = []

        try:
            response = await client.get(robots_url)
            if response.status_code != 200:
                logger.debug("robots_txt_not_found", url=robots_url, status=response.status_code)
                return urls

            content = response.text
            sitemap_pattern = re.compile(r"Sitemap:\s*(.+)", re.IGNORECASE)
            for match in sitemap_pattern.finditer(content):
                sitemap_url = match.group(1).strip()
                urls.append(
                    DiscoveredURL(
                        url=normalize_url(sitemap_url, base_url=base_url),
                        source="robots",
                        context="Sitemap directive",
                    )
                )

            logger.info("robots_txt_parsed", url=robots_url, sitemaps_found=len(urls))

        except Exception as e:
            logger.debug("robots_txt_fetch_failed", url=robots_url, error=str(e))

        return urls

    async def _fetch_sitemaps(
        self, client: httpx.AsyncClient, base_url: str
    ) -> list[DiscoveredURL]:
        """Fetch sitemap.xml and extract page URLs."""
        parsed = urlparse(base_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        urls: list[DiscoveredURL] = []

        try:
            response = await client.get(sitemap_url)
            if response.status_code != 200:
                logger.debug("sitemap_not_found", url=sitemap_url, status=response.status_code)
                return urls

            soup = BeautifulSoup(response.text, "xml")

            for loc in soup.find_all("loc"):
                if loc.string:
                    urls.append(
                        DiscoveredURL(
                            url=normalize_url(loc.string.strip(), base_url=base_url),
                            source="sitemap",
                        )
                    )

            for sitemap in soup.find_all("sitemap"):
                loc_tag = sitemap.find("loc")
                if loc_tag and loc_tag.string:
                    sub_urls = await self._fetch_sitemaps(client, loc_tag.string.strip())
                    urls.extend(sub_urls)

            logger.info("sitemap_parsed", url=sitemap_url, urls_found=len(urls))

        except Exception as e:
            logger.debug("sitemap_fetch_failed", url=sitemap_url, error=str(e))

        return urls

    async def _fetch_and_parse_page(
        self, client: httpx.AsyncClient, url: str, source: str
    ) -> list[DiscoveredURL]:
        """Fetch a page and extract links from nav, footer, and internal links."""
        urls: list[DiscoveredURL] = []

        try:
            response = await client.get(url)
            if response.status_code != 200:
                logger.debug("page_fetch_failed", url=url, status=response.status_code)
                return urls

            html = response.text

            # Check if page is a SPA and needs Playwright rendering
            from app.collectors.fetcher import PageAnalyzer
            analyzer = PageAnalyzer()
            analysis = analyzer.analyze(html)
            if analysis["needs_rendering"]:
                logger.info("discovery_playwright_fallback", url=url, score=analysis["score"])
                try:
                    from app.collectors.fetcher import PlaywrightRenderer
                    renderer = PlaywrightRenderer()
                    html = await renderer.render(url)
                except Exception as e:
                    logger.debug("discovery_playwright_failed", url=url, error=str(e))

            soup = BeautifulSoup(html, "html.parser")

            if self._settings.parse_nav:
                nav_urls = self._extract_nav_links(soup, url)
                urls.extend(nav_urls)

            if self._settings.parse_footer:
                footer_urls = self._extract_footer_links(soup, url)
                urls.extend(footer_urls)

            if self._settings.parse_internal_links:
                internal_urls = self._extract_internal_links(soup, url)
                urls.extend(internal_urls)

            meta_urls = self._extract_meta_links(soup, url)
            urls.extend(meta_urls)

            # If no nav/footer found (SPA with div-based layout), extract all internal links
            if not urls:
                all_internal = self._extract_internal_links(soup, url)
                urls.extend(all_internal)

        except Exception as e:
            logger.debug("page_parse_failed", url=url, error=str(e))

        return urls

    def _extract_nav_links(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredURL]:
        """Extract links from navigation elements."""
        urls: list[DiscoveredURL] = []
        nav_selectors = ["nav", "header", '[role="navigation"]', ".nav", ".navigation", "#nav"]

        for selector in nav_selectors:
            for nav in soup.select(selector):
                for a_tag in nav.find_all("a", href=True):
                    href = str(a_tag.get("href", ""))
                    if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        text = a_tag.get_text(strip=True)
                        urls.append(
                            DiscoveredURL(
                                url=normalize_url(href, base_url=base_url),
                                source="nav",
                                context=text[:100],
                            )
                        )

        return urls

    def _extract_footer_links(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredURL]:
        """Extract links from footer elements."""
        urls: list[DiscoveredURL] = []
        footer_selectors = ["footer", '[role="contentinfo"]', ".footer", "#footer"]

        for selector in footer_selectors:
            for footer in soup.select(selector):
                for a_tag in footer.find_all("a", href=True):
                    href = str(a_tag.get("href", ""))
                    if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        text = a_tag.get_text(strip=True)
                        urls.append(
                            DiscoveredURL(
                                url=normalize_url(href, base_url=base_url),
                                source="footer",
                                context=text[:100],
                            )
                        )

        return urls

    def _extract_internal_links(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredURL]:
        """Extract all internal links from the page."""
        urls: list[DiscoveredURL] = []
        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc.lower()

        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag.get("href", ""))
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                normalized = normalize_url(href, base_url=base_url)
                if self._is_same_domain(normalized, domain):
                    text = a_tag.get_text(strip=True)
                    urls.append(
                        DiscoveredURL(
                            url=normalized,
                            source="internal_link",
                            context=text[:100],
                        )
                    )

        return urls

    def _extract_meta_links(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredURL]:
        """Extract canonical and alternate links from meta tags."""
        urls: list[DiscoveredURL] = []

        for tag in soup.select("link[href]"):
            href = tag.get("href")
            rel_raw = tag.get("rel")
            if isinstance(rel_raw, str):
                rel_list: list[str] = [rel_raw]
            elif isinstance(rel_raw, list):
                rel_list = [str(r) for r in rel_raw]
            else:
                rel_list = []
            if href and any(r in rel_list for r in ("canonical", "alternate")):
                urls.append(
                    DiscoveredURL(
                        url=normalize_url(str(href), base_url=base_url),
                        source="meta",
                    )
                )

        return urls

    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if a URL belongs to the same domain."""
        parsed = urlparse(url)
        url_domain = parsed.netloc.lower()
        # Normalize: strip www. prefix for comparison
        url_domain_clean = url_domain.removeprefix("www.")
        domain_clean = domain.removeprefix("www.")
        return url_domain_clean == domain_clean or url_domain_clean.endswith(f".{domain_clean}")

    def _deduplicate(self, urls: list[DiscoveredURL]) -> list[DiscoveredURL]:
        """Remove duplicate URLs, keeping the one with the best source."""
        source_priority = {
            "robots": 0,
            "sitemap": 1,
            "nav": 2,
            "footer": 3,
            "meta": 4,
            "internal_link": 5,
        }
        seen: dict[str, DiscoveredURL] = {}

        for discovered in urls:
            normalized = discovered.url.rstrip("/")
            if normalized in seen:
                existing = seen[normalized]
                if source_priority.get(discovered.source, 99) < source_priority.get(
                    existing.source, 99
                ):
                    seen[normalized] = discovered
            else:
                seen[normalized] = discovered

        return list(seen.values())

    def _rank(self, urls: list[DiscoveredURL], domain: str) -> list[DiscoveredURL]:
        """Rank URLs by relevance for competitor intelligence collection."""
        high_value_patterns = [
            (r"/(service|pricing|plan|product|feature)", 10),
            (r"/(about|company|team|story|mission)", 8),
            (r"/(blog|article|news|resource|case-study)", 7),
            (r"/(contact|support|help|faq)", 5),
            (r"/(privacy|terms|legal|policy)", 3),
            (r"/(career|job|hiring)", 2),
        ]

        def score_url(discovered: DiscoveredURL) -> int:
            s = 0
            url_lower = discovered.url.lower()

            source_scores = {
                "nav": 5,
                "footer": 3,
                "sitemap": 4,
                "robots": 2,
                "meta": 1,
                "internal_link": 0,
            }
            s += source_scores.get(discovered.source, 0)

            for pattern, weight in high_value_patterns:
                if re.search(pattern, url_lower):
                    s += weight
                    break

            depth_penalty = discovered.depth * 2
            s -= depth_penalty

            path_parts = [p for p in urlparse(discovered.url).path.split("/") if p]
            if len(path_parts) <= 2:
                s += 2

            return s

        urls.sort(key=score_url, reverse=True)
        return urls

    def _count_by_source(self, urls: list[DiscoveredURL]) -> dict[str, int]:
        """Count URLs by source type."""
        counts: dict[str, int] = {}
        for u in urls:
            counts[u.source] = counts.get(u.source, 0) + 1
        return counts
