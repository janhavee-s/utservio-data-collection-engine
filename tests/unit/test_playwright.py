"""Tests for Playwright browser rendering and fallback logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ConnectError, TimeoutException

from app.collectors.fetcher import (
    HybridFetcher,
    PageAnalyzer,
    PlaywrightRenderer,
    _validate_url_not_private,
)
from app.exceptions import SSRFError


class TestSSRFProtection:
    def test_blocks_private_ip_10(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://10.0.0.1/admin")

    def test_blocks_private_ip_172(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://172.16.0.1/metadata")

    def test_blocks_private_ip_192(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://192.168.1.1/internal")

    def test_blocks_loopback(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://127.0.0.1:8080/admin")

    def test_blocks_metadata_endpoint(self):
        with pytest.raises(SSRFError, match=r"SSRF blocked.*metadata"):
            _validate_url_not_private("http://169.254.169.254/latest/meta-data/")

    def test_blocks_localhost(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://localhost/admin")

    def test_blocks_internal_tld(self):
        with pytest.raises(SSRFError, match="SSRF blocked"):
            _validate_url_not_private("http://myapp.internal/data")

    def test_allows_public_url(self):
        _validate_url_not_private("https://example.com/page")

    def test_allows_public_ip(self):
        _validate_url_not_private("http://8.8.8.8/dns-query")

    def test_blocks_invalid_url(self):
        with pytest.raises(SSRFError, match="no hostname"):
            _validate_url_not_private("not-a-url")


class TestPageAnalyzer:
    def test_react_page_needs_rendering(self):
        html = """
        <html>
        <head>
            <script src="/static/js/bundle.js"></script>
            <script>self.__next_f=[]</script>
        </head>
        <body>
            <div id="root" data-reactroot></div>
            <noscript>Please enable JavaScript</noscript>
        </body>
        </html>
        """
        analyzer = PageAnalyzer()
        result = analyzer.analyze(html)
        assert result["needs_rendering"] is True
        assert result["score"] >= 50

    def test_static_page_no_rendering(self):
        html = """
        <html>
        <head><title>Page</title></head>
        <body>
        <h1>Hello World</h1>
        <p>This is a static page with lots of content. Lorem ipsum dolor sit amet,
        consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et
        dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation
        ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
        </body>
        </html>
        """
        analyzer = PageAnalyzer()
        result = analyzer.analyze(html)
        assert result["needs_rendering"] is False

    def test_nextjs_page_needs_rendering(self):
        html = """
        <html>
        <head><script>self.__next_f=[]</script></head>
        <body><div id="__next"></div></body>
        </html>
        """
        analyzer = PageAnalyzer()
        result = analyzer.analyze(html)
        assert result["needs_rendering"] is True


class TestPlaywrightRenderer:
    @pytest.mark.asyncio
    async def test_verify_browser_success(self):
        """Test verify_browser returns True when Chromium is available."""
        mock_browser = AsyncMock()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        mock_pw_class = AsyncMock()
        mock_pw_class.start.return_value = mock_pw_instance

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_class):
            ok, msg = await PlaywrightRenderer.verify_browser()
            assert ok is True
            assert "verified" in msg.lower()
            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_browser_failure(self):
        """Test verify_browser returns False with instructions when Chromium missing."""
        mock_pw_class = AsyncMock()
        mock_pw_class.start.side_effect = Exception("browser not found")

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_class):
            ok, msg = await PlaywrightRenderer.verify_browser()
            assert ok is False
            assert "playwright install chromium" in msg.lower()
            assert "browser not found" in msg.lower()

    @pytest.mark.asyncio
    async def test_verify_browser_launch_failure(self):
        """Test verify_browser returns False when launch fails."""
        mock_browser = AsyncMock()
        mock_browser.close.side_effect = Exception("launch failed")

        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch.side_effect = Exception("executable not found")

        mock_pw_class = AsyncMock()
        mock_pw_class.start.return_value = mock_pw_instance

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_class):
            ok, msg = await PlaywrightRenderer.verify_browser()
            assert ok is False
            assert "playwright install chromium" in msg.lower()

    @pytest.mark.asyncio
    async def test_render_calls_page_methods(self):
        """Test that render creates page, navigates, and closes."""
        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context

        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_pw_class = AsyncMock()
        mock_pw_class.start.return_value = mock_playwright_instance

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_class):
            renderer = PlaywrightRenderer()
            html = await renderer.render("https://example.com", timeout=5000)

            assert html == "<html></html>"
            mock_page.goto.assert_called_once()
            mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self):
        """Test that close() cleans up browser, context, and playwright."""
        renderer = PlaywrightRenderer()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        renderer._browser = mock_browser
        renderer._context = mock_context
        renderer._playwright = mock_playwright

        await renderer.close()

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert renderer._browser is None
        assert renderer._context is None
        assert renderer._playwright is None

    @pytest.mark.asyncio
    async def test_close_handles_already_closed(self):
        """Test that close() is safe to call multiple times."""
        renderer = PlaywrightRenderer()
        await renderer.close()  # Should not raise
        await renderer.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_render_handles_timeout(self):
        """Test that render propagates timeout errors."""
        mock_page = AsyncMock()
        mock_page.goto.side_effect = TimeoutException("timeout")

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context

        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_pw_class = AsyncMock()
        mock_pw_class.start.return_value = mock_playwright_instance

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_class):
            renderer = PlaywrightRenderer()
            with pytest.raises(TimeoutException):
                await renderer.render("https://example.com", timeout=1000)


class TestHybridFetcherRetryLogic:
    def test_is_retryable_network_error(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(None, TimeoutException("timeout")) is True
        assert fetcher._is_retryable(None, ConnectError("connection")) is True

    def test_is_retryable_server_error(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(500, None) is True
        assert fetcher._is_retryable(502, None) is True
        assert fetcher._is_retryable(503, None) is True

    def test_is_retryable_rate_limit(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(429, None) is True

    def test_not_retryable_client_error(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(400, None) is False
        assert fetcher._is_retryable(404, None) is False
        assert fetcher._is_retryable(403, None) is False

    def test_not_retryable_unknown_error_type(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(400, ValueError("bad input")) is False

    def test_retryable_unknown_status(self):
        fetcher = HybridFetcher()
        assert fetcher._is_retryable(None, None) is True

    def test_not_retryable_dns_error(self):
        """DNS resolution failures should not be retried."""
        fetcher = HybridFetcher()
        dns_error = OSError(8, "nodename nor servname provided")
        assert fetcher._is_retryable(None, dns_error) is False

        dns_error_neg2 = OSError(-2, "Name or service not known")
        assert fetcher._is_retryable(None, dns_error_neg2) is False

        dns_error_neg3 = OSError(-3, "Temporary failure in name resolution")
        assert fetcher._is_retryable(None, dns_error_neg3) is False


class TestHybridFetcher404Detection:
    def test_detects_404_status(self):
        fetcher = HybridFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://example.com/not-found"

        is_404, _final = fetcher._detect_404_redirect(mock_response, "https://example.com/page")
        assert is_404 is True

    def test_detects_404_redirect(self):
        fetcher = HybridFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/404"

        is_404, final = fetcher._detect_404_redirect(mock_response, "https://example.com/page")
        assert is_404 is True
        assert "/404" in final

    def test_no_404_on_normal_page(self):
        fetcher = HybridFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/page"

        is_404, _final = fetcher._detect_404_redirect(mock_response, "https://example.com/page")
        assert is_404 is False
