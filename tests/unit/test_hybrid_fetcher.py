from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.fetcher import FetchResult, HybridFetcher, PageAnalyzer, PlaywrightRenderer


class TestPageAnalyzer:
    def test_static_page_returns_low_score(self) -> None:
        html = """
        <html>
        <head><title>Static Page</title></head>
        <body>
            <h1>Welcome</h1>
            <p>This is a static page with lots of content.
            It has no JavaScript frameworks or dynamic indicators.
            The content is substantial and well-structured.</p>
        </body>
        </html>
        """
        analyzer = PageAnalyzer(min_content_length=100)
        result = analyzer.analyze(html)

        assert result["needs_rendering"] is False
        assert result["score"] < 50
        assert result["has_framework"] is False
        assert result["has_indicators"] is False

    def test_react_page_returns_high_score(self) -> None:
        html = """
        <html>
        <head>
            <script src="react.js"></script>
        </head>
        <body>
            <div id="root"></div>
            <script>
                ReactDOM.render(<App />, document.getElementById('root'));
            </script>
        </body>
        </html>
        """
        analyzer = PageAnalyzer(min_content_length=100)
        result = analyzer.analyze(html)

        assert result["needs_rendering"] is True
        assert result["score"] >= 50
        assert result["has_framework"] is True

    def test_nextjs_page_returns_high_score(self) -> None:
        html = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {"props": {"pageProps": {}}}
            </script>
        </head>
        <body>
            <div id="__next"></div>
        </body>
        </html>
        """
        analyzer = PageAnalyzer(min_content_length=100)
        result = analyzer.analyze(html)

        assert result["needs_rendering"] is True
        assert result["score"] >= 50
        assert result["has_indicators"] is True

    def test_spa_with_loading_indicator(self) -> None:
        html = """
        <html>
        <body>
            <div id="app">
                <noscript>Please enable JavaScript to view this application</noscript>
                Loading...
                JavaScript is required to view this page
            </div>
            <script>
                window.__INITIAL_STATE__ = {};
                document.getElementById('app').innerHTML = 'Loaded';
            </script>
        </body>
        </html>
        """
        analyzer = PageAnalyzer(min_content_length=500)
        result = analyzer.analyze(html)

        assert result["needs_rendering"] is True
        assert result["has_quality_issues"] is True
        assert result["has_indicators"] is True

    def test_vue_page_detected(self) -> None:
        html = """
        <html>
        <body>
            <div id="app" data-v-abc123></div>
            <script src="vue.js"></script>
        </body>
        </html>
        """
        analyzer = PageAnalyzer(min_content_length=100)
        result = analyzer.analyze(html)

        assert result["needs_rendering"] is True
        assert result["has_framework"] is True
        assert result["has_indicators"] is True


class TestHybridFetcher:
    @pytest.mark.asyncio
    async def test_fetch_static_page_uses_httpx(self) -> None:
        fetcher = HybridFetcher()
        # Use a realistic static page with enough content to avoid minimal content detection
        static_html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
        <h1>Welcome to our website</h1>
        <p>This is a test page with enough content to be considered static.
        It has multiple paragraphs and proper HTML structure that indicates
        it's a fully rendered page without requiring JavaScript.</p>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = static_html
        mock_response.status_code = 200

        with patch.object(fetcher, "_fetch_static", new_callable=AsyncMock) as mock_static:
            mock_static.return_value = FetchResult(
                html=mock_response.text,
                url="https://example.com",
                method="httpx",
                status_code=200,
                content_length=len(mock_response.text),
            )

            result = await fetcher.fetch("https://example.com")

            assert result.method == "httpx"
            assert result.html == mock_response.text
            mock_static.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_dynamic_page_uses_playwright(self) -> None:
        fetcher = HybridFetcher()

        static_html = """
        <html>
        <head><script src="react.js"></script></head>
        <body><div id="root"></div></body>
        </html>
        """

        dynamic_html = """
        <html>
        <head><script src="react.js"></script></head>
        <body>
            <div id="root">
                <h1>Rendered Content</h1>
                <p>This is rendered by React</p>
            </div>
        </body>
        </html>
        """

        with (
            patch.object(fetcher, "_fetch_static", new_callable=AsyncMock) as mock_static,
            patch.object(fetcher, "_fetch_dynamic", new_callable=AsyncMock) as mock_dynamic,
        ):
            mock_static.return_value = FetchResult(
                html=static_html,
                url="https://example.com",
                method="httpx",
                status_code=200,
                content_length=len(static_html),
            )

            mock_dynamic.return_value = FetchResult(
                html=dynamic_html,
                url="https://example.com",
                method="playwright",
                status_code=200,
                content_length=len(dynamic_html),
                js_rendered=True,
            )

            result = await fetcher.fetch("https://example.com")

            assert result.method == "playwright"
            assert result.js_rendered is True
            assert "Rendered Content" in result.html
            mock_dynamic.assert_called_once()

    @pytest.mark.asyncio
    async def test_playwright_fallback_returns_static_on_failure(self) -> None:
        fetcher = HybridFetcher()

        static_html = """
        <html>
        <head><script src="react.js"></script></head>
        <body><div id="root"></div></body>
        </html>
        """

        with (
            patch.object(fetcher, "_fetch_static", new_callable=AsyncMock) as mock_static,
            patch.object(fetcher, "_fetch_dynamic", new_callable=AsyncMock) as mock_dynamic,
        ):
            mock_static.return_value = FetchResult(
                html=static_html,
                url="https://example.com",
                method="httpx",
                status_code=200,
                content_length=len(static_html),
            )

            mock_dynamic.side_effect = Exception("Playwright failed")

            result = await fetcher.fetch("https://example.com")

            assert result.method == "httpx"
            assert result.js_rendered is False


class TestPlaywrightRenderer:
    @pytest.mark.asyncio
    async def test_renderer_initializes_browser(self) -> None:
        renderer = PlaywrightRenderer()

        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_pw_instance = AsyncMock()
            mock_pw.return_value = mock_pw_instance
            mock_pw_instance.start = AsyncMock(return_value=AsyncMock())
            mock_pw_instance.start.return_value.chromium.launch = AsyncMock(
                return_value=mock_browser
            )
            mock_browser.new_context = AsyncMock(return_value=mock_context)

            context = await renderer._ensure_browser()

            assert context == mock_context
            mock_browser.new_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_renderer_cleans_up_resources(self) -> None:
        renderer = PlaywrightRenderer()

        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        renderer._playwright = mock_playwright
        renderer._browser = mock_browser
        renderer._context = mock_context

        await renderer.close()

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert renderer._context is None
        assert renderer._browser is None
        assert renderer._playwright is None


class TestFetchResult:
    def test_fetch_result_creation(self) -> None:
        result = FetchResult(
            html="<html></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=15,
            js_rendered=False,
        )

        assert result.html == "<html></html>"
        assert result.url == "https://example.com"
        assert result.method == "httpx"
        assert result.status_code == 200
        assert result.content_length == 15
        assert result.js_rendered is False

    def test_fetch_result_defaults(self) -> None:
        result = FetchResult(
            html="<html></html>",
            url="https://example.com",
            method="playwright",
        )

        assert result.status_code is None
        assert result.content_length == 0
        assert result.js_rendered is False
