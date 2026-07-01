import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx
from bs4 import BeautifulSoup

from app.configuration.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a fetch operation."""

    html: str
    url: str
    method: str  # "httpx" or "playwright"
    status_code: int | None = None
    content_length: int = 0
    js_rendered: bool = False


class PageAnalyzer:
    """Analyzes HTML to detect JavaScript-heavy pages requiring rendering."""

    JS_FRAMEWORKS: ClassVar[list[str]] = [
        r"react",
        r"vue\.js",
        r"angular",
        r"next\.js",
        r"nuxt",
        r"svelte",
        r"ember",
        r"backbone",
        r"preact",
        r"solid\.js",
    ]

    DYNAMIC_INDICATORS: ClassVar[list[str]] = [
        r"__next",
        r"__nuxt",
        r"__vue__",
        r"__react",
        r"__angular",
        r"window\.__INITIAL_STATE__",
        r"window\.__NUXT__",
        r"data-reactroot",
        r"data-reactid",
        r"ng-version",
        r"data-v-",
        r"data-svelte",
        r"__gatsby",
        r"___gatsby",
    ]

    CONTENT_QUALITY_INDICATORS: ClassVar[list[str]] = [
        r"<script[^>]*>.*?</script>",
        r"<noscript>.*?</noscript>",
        r"Loading\.\.\.\.",
        r"Please enable JavaScript",
        r"JavaScript is required",
    ]

    def __init__(self, *, min_content_length: int = 500) -> None:
        self._min_content_length = min_content_length
        self._compiled_frameworks = [re.compile(p, re.IGNORECASE) for p in self.JS_FRAMEWORKS]
        self._compiled_indicators = [re.compile(p, re.IGNORECASE) for p in self.DYNAMIC_INDICATORS]
        self._compiled_quality = [
            re.compile(p, re.IGNORECASE) for p in self.CONTENT_QUALITY_INDICATORS
        ]

    def analyze(self, html: str) -> dict[str, Any]:
        """Analyze HTML and return whether JavaScript rendering is needed."""
        has_framework = self._check_js_frameworks(html)
        has_indicators = self._check_dynamic_indicators(html)
        has_quality_issues = self._check_content_quality(html)

        score = 0
        if has_framework:
            score += 40
        if has_indicators:
            score += 35
        if has_quality_issues:
            score += 25

        needs_rendering = score >= 50

        return {
            "needs_rendering": needs_rendering,
            "score": score,
            "has_framework": has_framework,
            "has_indicators": has_indicators,
            "has_quality_issues": has_quality_issues,
        }

    def _check_js_frameworks(self, html: str) -> bool:
        """Check for JavaScript framework signatures."""
        soup = BeautifulSoup(html, "html.parser")

        script_tags = soup.find_all("script")
        script_contents = " ".join([str(s.string or "") for s in script_tags if s.string])
        script_srcs = " ".join([str(s.get("src", "")) for s in script_tags])

        combined = f"{script_contents} {script_srcs}"

        return any(pattern.search(combined) for pattern in self._compiled_frameworks)

    def _check_dynamic_indicators(self, html: str) -> bool:
        """Check for dynamic rendering indicators."""
        return any(pattern.search(html) for pattern in self._compiled_indicators)

    def _check_content_quality(self, html: str) -> bool:
        """Check for poor content quality indicators."""
        soup = BeautifulSoup(html, "html.parser")

        text_content = soup.get_text(strip=True)
        if len(text_content) < self._min_content_length:
            return True

        return any(pattern.search(html) for pattern in self._compiled_quality)


class PlaywrightRenderer:
    """Renders JavaScript-heavy pages using Playwright."""

    def __init__(self) -> None:
        self._browser: Any = None
        self._context: Any = None
        self._playwright: Any = None

    async def _ensure_browser(self) -> Any:
        """Ensure browser is initialized."""
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
        return self._context

    async def render(self, url: str, *, timeout: int = 30000) -> str:
        """Render a page and return the HTML."""
        context = await self._ensure_browser()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout)

            await page.wait_for_timeout(2000)

            html = str(await page.content())
            logger.info("Playwright rendered page: %s", url)
            return html
        except Exception as e:
            logger.error("Playwright render failed for %s: %s", url, e)
            raise
        finally:
            await page.close()

    async def close(self) -> None:
        """Clean up browser resources."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.warning("Error closing Playwright: %s", e)


class HybridFetcher:
    """Fetches pages using httpx first, falling back to Playwright if needed."""

    def __init__(self) -> None:
        self._settings = get_settings().collector
        self._client: httpx.AsyncClient | None = None
        self._analyzer = PageAnalyzer()
        self._renderer: PlaywrightRenderer | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.collection_timeout),
                headers={"User-Agent": self._settings.user_agent},
                follow_redirects=True,
                verify=True,
            )
        return self._client

    async def _get_renderer(self) -> PlaywrightRenderer:
        """Get or create Playwright renderer."""
        if self._renderer is None:
            self._renderer = PlaywrightRenderer()
        return self._renderer

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a page using hybrid strategy."""
        static_result = await self._fetch_static(url)

        analysis = self._analyzer.analyze(static_result.html)
        logger.debug(
            "Page analysis for %s: score=%d, needs_rendering=%s",
            url,
            analysis["score"],
            analysis["needs_rendering"],
        )

        if not analysis["needs_rendering"]:
            return static_result

        logger.info("Static fetch insufficient for %s, trying Playwright", url)

        try:
            dynamic_result = await self._fetch_dynamic(url)
            return dynamic_result
        except Exception as e:
            logger.warning(
                "Playwright fallback failed for %s, returning static result: %s",
                url,
                e,
            )
            return static_result

    async def _fetch_static(self, url: str) -> FetchResult:
        """Fetch page using httpx."""
        last_error: Exception | None = None

        for attempt in range(self._settings.retry_attempts):
            try:
                client = await self._get_client()
                response = await client.get(url)
                response.raise_for_status()

                return FetchResult(
                    html=response.text,
                    url=url,
                    method="httpx",
                    status_code=response.status_code,
                    content_length=len(response.text),
                    js_rendered=False,
                )
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                logger.warning(
                    "Static fetch failed (attempt %d/%d): %s - %s",
                    attempt + 1,
                    self._settings.retry_attempts,
                    url,
                    e,
                )
                if attempt < self._settings.retry_attempts - 1:
                    delay = self._settings.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError(f"Failed to fetch {url}")

    async def _fetch_dynamic(self, url: str) -> FetchResult:
        """Fetch page using Playwright."""
        renderer = await self._get_renderer()
        html = await renderer.render(url)

        return FetchResult(
            html=html,
            url=url,
            method="playwright",
            status_code=200,
            content_length=len(html),
            js_rendered=True,
        )

    async def close(self) -> None:
        """Clean up all resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

        if self._renderer:
            await self._renderer.close()
            self._renderer = None
