import asyncio
import contextlib
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.configuration.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class FetchResult:
    """Result of a fetch operation."""

    html: str
    url: str
    method: str  # "httpx" or "playwright"
    status_code: int | None = None
    content_length: int = 0
    js_rendered: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    final_url: str = ""
    is_404_redirect: bool = False
    etag: str | None = None
    last_modified: str | None = None
    cache_control: str | None = None
    content_hash: str = ""
    not_modified: bool = False
    language: str = ""
    language_confidence: float = 0.0
    page_type: str = ""
    page_type_confidence: float = 0.0


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

    async def render(
        self,
        url: str,
        *,
        timeout: int = 30000,
        primary_selector: str = "body",
    ) -> str:
        """Render a page and return the HTML.

        Uses domcontentloaded for faster initial load, then waits for
        a primary content selector before extracting HTML.
        """
        context = await self._ensure_browser()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            with contextlib.suppress(Exception):
                await page.wait_for_selector(primary_selector, timeout=min(timeout, 10000))

            html = str(await page.content())
            logger.info("playwright_rendered", url=url, html_length=len(html))
            return html
        except Exception as e:
            logger.error("playwright_render_failed", url=url, error=str(e))
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
            logger.warning("playwright_cleanup_error", error=str(e))


class RateLimiter:
    """Token-bucket rate limiter for HTTP requests."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


@dataclass
class CacheEntry:
    """Stored cache metadata for a URL."""

    url: str
    etag: str | None = None
    last_modified: str | None = None
    cache_control: str | None = None
    content_hash: str = ""
    last_checked: str = ""


class HttpCacheLayer:
    """HTTP cache layer supporting conditional GET requests.

    Stores ETag, Last-Modified, and Cache-Control headers per URL.
    Enables 304 Not Modified responses to avoid re-downloading unchanged pages.
    """

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get(self, url: str) -> CacheEntry | None:
        """Retrieve cached metadata for a URL."""
        return self._cache.get(url)

    def store(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
        cache_control: str | None = None,
        content_hash: str = "",
    ) -> CacheEntry:
        """Store or update cache metadata for a URL."""
        from datetime import UTC, datetime

        entry = self._cache.get(url)
        if entry:
            if etag:
                entry.etag = etag
            if last_modified:
                entry.last_modified = last_modified
            if cache_control:
                entry.cache_control = cache_control
            if content_hash:
                entry.content_hash = content_hash
            entry.last_checked = datetime.now(UTC).isoformat()
        else:
            entry = CacheEntry(
                url=url,
                etag=etag,
                last_modified=last_modified,
                cache_control=cache_control,
                content_hash=content_hash,
                last_checked=datetime.now(UTC).isoformat(),
            )
            self._cache[url] = entry
        return entry

    def build_conditional_headers(self, url: str) -> dict[str, str]:
        """Build conditional GET headers for a URL.

        Returns headers dict with If-None-Match and/or If-Modified-Since
        if cached metadata exists for the URL.
        """
        entry = self._cache.get(url)
        if not entry:
            return {}

        headers: dict[str, str] = {}
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = entry.last_modified
        return headers

    def is_cache_expired(self, url: str) -> bool:
        """Check if cache entry has expired based on Cache-Control."""
        from datetime import UTC, datetime

        entry = self._cache.get(url)
        if not entry or not entry.cache_control or not entry.last_checked:
            return True

        if "no-cache" in entry.cache_control or "no-store" in entry.cache_control:
            return True

        max_age_match = re.search(r"max-age=(\d+)", entry.cache_control)
        if max_age_match:
            max_age = int(max_age_match.group(1))
            try:
                last_checked = datetime.fromisoformat(entry.last_checked)
                elapsed = (datetime.now(UTC) - last_checked).total_seconds()
                return elapsed > max_age
            except ValueError:
                return True

        return False

    def remove(self, url: str) -> None:
        """Remove a URL from the cache."""
        self._cache.pop(url, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Number of cached entries."""
        return len(self._cache)


class HybridFetcher:
    """Fetches pages using httpx first, falling back to Playwright if needed.

    HTTP handling:
    - Detects 404 redirects (server redirects to /404 or returns 404 after redirect)
    - Does not retry permanent failures (4xx except 429)
    - Tracks redirect chains
    - Only retries transient failures (5xx, network errors, 429)
    - Respects rate limiting via token-bucket algorithm
    - Supports conditional GET via ETag/Last-Modified for incremental crawling
    """

    def __init__(self) -> None:
        self._settings = get_settings().collector
        self._client: httpx.AsyncClient | None = None
        self._analyzer = PageAnalyzer()
        self._renderer: PlaywrightRenderer | None = None
        self._rate_limiter = RateLimiter(self._settings.rate_limit_per_second)
        self._cache_layer = HttpCacheLayer()

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
        """Fetch a page using hybrid strategy with incremental crawling support.

        Workflow:
        1. Check cache for ETag/Last-Modified
        2. Send conditional GET request
        3. If 304 Not Modified → skip parsing, update metadata, return
        4. If content hash unchanged → skip parsing, skip DB writes, log reason
        5. Otherwise → full fetch with Playwright fallback
        6. Detect language and classify page type
        """
        from app.parsers.language_detector import LanguageDetector
        from app.parsers.page_classifier import PageClassifier

        cache_expired = self._cache_layer.is_cache_expired(url)
        conditional_headers = self._cache_layer.build_conditional_headers(url)

        static_result = await self._fetch_static(url, conditional_headers)

        if static_result.is_404_redirect:
            logger.info("skipping_404_redirect", url=url, final_url=static_result.final_url)
            return static_result

        if static_result.not_modified:
            logger.info(
                "incremental_skip_304",
                url=url,
                reason="server_responded_304",
            )
            return static_result

        if conditional_headers and not cache_expired:
            from app.utilities.content_hasher import compute_page_content_hash

            new_hash = compute_page_content_hash(static_result.html, url)
            cached = self._cache_layer.get(url)
            if cached and cached.content_hash == new_hash and new_hash:
                logger.info(
                    "incremental_skip_unchanged",
                    url=url,
                    reason="content_hash_unchanged",
                    content_hash=new_hash[:16],
                )
                return FetchResult(
                    html="",
                    url=url,
                    method=static_result.method,
                    status_code=static_result.status_code,
                    content_length=static_result.content_length,
                    js_rendered=static_result.js_rendered,
                    redirect_chain=static_result.redirect_chain,
                    final_url=static_result.final_url,
                    etag=static_result.etag,
                    last_modified=static_result.last_modified,
                    cache_control=static_result.cache_control,
                    content_hash=new_hash,
                    not_modified=True,
                )

        self._cache_layer.store(
            url=url,
            etag=static_result.etag,
            last_modified=static_result.last_modified,
            cache_control=static_result.cache_control,
            content_hash=static_result.content_hash,
        )

        if static_result.html:
            lang_detector = LanguageDetector()
            lang_result = lang_detector.detect(static_result.html)
            static_result.language = lang_result.language
            static_result.language_confidence = lang_result.confidence

            classifier = PageClassifier()
            class_result = classifier.classify(static_result.html, url)
            static_result.page_type = class_result.page_type
            static_result.page_type_confidence = class_result.confidence

            from app.utilities.metrics import metrics
            metrics.inc_counter("pages_analyzed_total", language=lang_result.language, page_type=class_result.page_type)

        analysis = self._analyzer.analyze(static_result.html)
        logger.debug(
            "page_analysis",
            url=url,
            score=analysis["score"],
            needs_rendering=analysis["needs_rendering"],
            language=static_result.language,
            page_type=static_result.page_type,
        )

        if not analysis["needs_rendering"]:
            return static_result

        logger.info("playwright_fallback_triggered", url=url, score=analysis["score"])

        from app.utilities.metrics import metrics
        metrics.inc_counter("playwright_fallback_total")

        try:
            dynamic_result = await self._fetch_dynamic(url)
            if dynamic_result.html:
                lang_detector = LanguageDetector()
                lang_result = lang_detector.detect(dynamic_result.html)
                dynamic_result.language = lang_result.language
                dynamic_result.language_confidence = lang_result.confidence

                classifier = PageClassifier()
                class_result = classifier.classify(dynamic_result.html, url)
                dynamic_result.page_type = class_result.page_type
                dynamic_result.page_type_confidence = class_result.confidence
            return dynamic_result
        except Exception as e:
            logger.warning(
                "playwright_fallback_failed_returning_static",
                url=url,
                reason=str(e),
            )
            return static_result

    def _is_retryable(self, status_code: int | None, error: Exception | None) -> bool:
        """Determine if a failure is retryable.

        Retry only:
        - 5xx server errors
        - 429 Too Many Requests
        - Network/transport errors (timeout, connection reset, etc.)

        Do NOT retry:
        - 4xx client errors (except 429)
        - 404 Not Found
        - Permanent redirects
        """
        if error is not None and isinstance(
            error, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)
        ):
            return True

        if status_code is None:
            return True  # Unknown status — might be transient

        if status_code == 429:
            return True

        return status_code >= 500  # 4xx (except 429) — permanent, don't retry

    def _detect_404_redirect(self, response: httpx.Response, url: str) -> tuple[bool, str]:
        """Detect if the server redirected to a 404 page.

        Returns (is_404_redirect, final_url).
        """
        final_url = str(response.url)
        redirected = final_url.rstrip("/") != url.rstrip("/")

        if redirected:
            path_404_indicators = ("/404", "/error", "/not-found", "/page-not-found")
            parsed_final = urlparse(final_url)
            final_path = parsed_final.path.lower()
            if any(indicator in final_path for indicator in path_404_indicators):
                return True, final_url

        if response.status_code == 404:
            return True, final_url

        return False, final_url

    async def _fetch_static(
        self, url: str, conditional_headers: dict[str, str] | None = None
    ) -> FetchResult:
        """Fetch page using httpx with smart retry logic and conditional GET."""
        await self._rate_limiter.acquire()

        last_error: Exception | None = None
        redirect_chain: list[str] = []

        for attempt in range(self._settings.retry_attempts):
            try:
                client = await self._get_client()
                headers = dict(conditional_headers) if conditional_headers else {}
                response = await client.get(url, headers=headers)

                redirect_chain = [str(r.url) for r in response.history]
                final_url = str(response.url)

                etag = response.headers.get("etag")
                last_modified = response.headers.get("last-modified")
                cache_control = response.headers.get("cache-control")

                if response.status_code == 304:
                    logger.info("conditional_get_304", url=url)
                    cached = self._cache_layer.get(url)
                    return FetchResult(
                        html=cached.content_hash if cached else "",
                        url=url,
                        method="httpx",
                        status_code=304,
                        content_length=0,
                        js_rendered=False,
                        redirect_chain=redirect_chain,
                        final_url=final_url,
                        etag=etag or (cached.etag if cached else None),
                        last_modified=last_modified or (cached.last_modified if cached else None),
                        cache_control=cache_control,
                        content_hash=cached.content_hash if cached else "",
                        not_modified=True,
                    )

                is_404, final = self._detect_404_redirect(response, url)
                if is_404:
                    logger.info(
                        "404_redirect_detected",
                        url=url,
                        final_url=final,
                        redirect_chain=redirect_chain,
                    )
                    return FetchResult(
                        html="",
                        url=url,
                        method="httpx",
                        status_code=response.status_code,
                        content_length=0,
                        js_rendered=False,
                        redirect_chain=redirect_chain,
                        final_url=final,
                        is_404_redirect=True,
                    )

                response.raise_for_status()

                from app.utilities.content_hasher import compute_page_content_hash

                content_hash = compute_page_content_hash(response.text, url)

                return FetchResult(
                    html=response.text,
                    url=url,
                    method="httpx",
                    status_code=response.status_code,
                    content_length=len(response.text),
                    js_rendered=False,
                    redirect_chain=redirect_chain,
                    final_url=final_url,
                    etag=etag,
                    last_modified=last_modified,
                    cache_control=cache_control,
                    content_hash=content_hash,
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code

                if not self._is_retryable(status_code, e):
                    logger.warning(
                        "permanent_http_error_not_retrying",
                        url=url,
                        status=status_code,
                        attempt=attempt + 1,
                    )
                    return FetchResult(
                        html="",
                        url=url,
                        method="httpx",
                        status_code=status_code,
                        content_length=0,
                        redirect_chain=redirect_chain,
                    )

                logger.warning(
                    "retryable_http_error",
                    url=url,
                    status=status_code,
                    attempt=attempt + 1,
                    max_attempts=self._settings.retry_attempts,
                )
            except httpx.TransportError as e:
                last_error = e
                logger.warning(
                    "transport_error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1,
                    max_attempts=self._settings.retry_attempts,
                )

            if attempt < self._settings.retry_attempts - 1:
                delay = self._settings.retry_delay * (2**attempt)
                await asyncio.sleep(delay)

        raise last_error or RuntimeError(f"Failed to fetch {url}")

    async def _fetch_dynamic(self, url: str) -> FetchResult:
        """Fetch page using Playwright."""
        await self._rate_limiter.acquire()

        renderer = await self._get_renderer()
        settings = get_settings().collector
        html = await renderer.render(
            url,
            timeout=settings.playwright_timeout,
            primary_selector=get_settings().collector.primary_selector,
        )

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

    @property
    def cache_layer(self) -> HttpCacheLayer:
        """Access the HTTP cache layer."""
        return self._cache_layer
