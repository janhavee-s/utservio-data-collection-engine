"""Tests for canonical URL handling and URL normalization."""

from app.utilities.url_normalizer import (
    extract_canonical_url,
    is_tracking_url,
    normalize_content_url,
    normalize_url,
)


class TestNormalizeUrl:
    def test_strips_tracking_params(self) -> None:
        url = "https://example.com/page?utm_source=google&utm_medium=cpc&id=123"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=123" in result

    def test_strips_fbclid(self) -> None:
        url = "https://example.com/page?fbclid=abc123"
        result = normalize_url(url)
        assert "fbclid" not in result

    def test_strips_gclid(self) -> None:
        url = "https://example.com/page?gclid=abc123"
        result = normalize_url(url)
        assert "gclid" not in result

    def test_removes_fragment(self) -> None:
        url = "https://example.com/page#section"
        result = normalize_url(url)
        assert "#" not in result

    def test_strips_trailing_slash(self) -> None:
        url = "https://example.com/page/"
        result = normalize_url(url)
        assert not result.endswith("/") or result == "https://example.com/"

    def test_removes_duplicate_slashes(self) -> None:
        url = "https://example.com//page//sub"
        result = normalize_url(url)
        assert "//" not in result.replace("https://", "")

    def test_lowercases_scheme_and_host(self) -> None:
        url = "HTTP://EXAMPLE.COM/Page"
        result = normalize_url(url)
        assert result.startswith("http://")
        assert "example.com" in result
        assert result == "http://example.com/Page"

    def test_strips_www(self) -> None:
        url = "https://www.example.com/page"
        result = normalize_url(url)
        assert "www." not in result

    def test_strips_default_port_80(self) -> None:
        url = "http://example.com:80/page"
        result = normalize_url(url)
        assert ":80" not in result

    def test_strips_default_port_443(self) -> None:
        url = "https://example.com:443/page"
        result = normalize_url(url)
        assert ":443" not in result

    def test_empty_url(self) -> None:
        assert normalize_url("") == ""

    def test_relative_url_with_base(self) -> None:
        result = normalize_url("/page", base_url="https://example.com")
        assert result == "https://example.com/page"

    def test_strips_many_tracking_params(self) -> None:
        url = "https://example.com/page?utm_source=x&utm_medium=y&utm_campaign=z&utm_term=t&utm_content=c&fbclid=f&gclid=g&ref=r&key=val"
        result = normalize_url(url)
        assert "utm_" not in result
        assert "fbclid" not in result
        assert "gclid" not in result
        assert "key=val" in result


class TestNormalizeContentUrl:
    def test_strips_trailing_slash(self) -> None:
        url = "https://example.com/blog/post/"
        result = normalize_content_url(url)
        assert not result.endswith("/")

    def test_keeps_root_slash(self) -> None:
        url = "https://example.com/"
        result = normalize_content_url(url)
        assert result == "https://example.com/"


class TestExtractCanonicalUrl:
    def test_extracts_canonical_link(self) -> None:
        html = '<html><head><link rel="canonical" href="https://example.com/canonical"></head><body></body></html>'
        result = extract_canonical_url(html, "https://example.com/page")
        assert result == "https://example.com/canonical"

    def test_extracts_og_url(self) -> None:
        html = '<html><head><meta property="og:url" content="https://example.com/og"></head><body></body></html>'
        result = extract_canonical_url(html, "https://example.com/page")
        assert result == "https://example.com/og"

    def test_returns_none_when_no_canonical(self) -> None:
        html = "<html><head></head><body></body></html>"
        result = extract_canonical_url(html, "https://example.com/page")
        assert result is None


class TestIsTrackingUrl:
    def test_detects_tracking_params(self) -> None:
        assert is_tracking_url("https://example.com/page?utm_source=google") is True

    def test_no_tracking_params(self) -> None:
        assert is_tracking_url("https://example.com/page?id=123") is False

    def test_no_query_string(self) -> None:
        assert is_tracking_url("https://example.com/page") is False
