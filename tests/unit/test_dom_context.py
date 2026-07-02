"""Tests for DOM context parser."""

from app.parsers.dom_context import DOMContext, DOMContextParser


class TestDOMContextParser:
    def setup_method(self) -> None:
        self.parser = DOMContextParser()

    def test_extracts_services_from_headings(self) -> None:
        html = """
        <html><body>
        <h2>Our Services</h2>
        <h3>AC Repair</h3>
        <p>Professional air conditioning repair</p>
        <h3>Plumbing</h3>
        <p>Expert plumbing solutions</p>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert len(result["services"]) >= 1

    def test_extracts_pricing(self) -> None:
        html = """
        <html><body>
        <h2>Pricing</h2>
        <h3>Basic Plan</h3>
        <p>$29.99 per month</p>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com/pricing")
        assert len(result["pricing"]) >= 1

    def test_extracts_articles(self) -> None:
        html = """
        <html><body>
        <article>
            <h2>Blog Post Title</h2>
            <p>Summary of the blog post</p>
            <a href="/blog/post1">Read more</a>
        </article>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com/blog")
        assert len(result["articles"]) >= 1

    def test_extracts_contact_info(self) -> None:
        html = """
        <html><body>
        <p>Contact us at info@example.com</p>
        <a href="mailto:support@example.com">Email</a>
        <a href="tel:+1234567890">Phone</a>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com/contact")
        assert "email" in result["contact"]

    def test_extracts_social_profiles(self) -> None:
        html = """
        <html><body>
        <a href="https://linkedin.com/company/test">LinkedIn</a>
        <a href="https://facebook.com/testpage">Facebook</a>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert len(result["social_profiles"]) >= 1

    def test_extracts_company_name(self) -> None:
        html = """
        <html><head><meta property="og:site_name" content="Test Company"></head>
        <body></body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert result["company_name"] == "Test Company"

    def test_extracts_description(self) -> None:
        html = """
        <html><head><meta name="description" content="Test description"></head>
        <body></body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert result["description"] == "Test description"

    def test_empty_html(self) -> None:
        result = self.parser.parse("<html><body></body></html>", "https://example.com")
        assert result["services"] == []
        assert result["pricing"] == []
        assert result["articles"] == []

    def test_dom_context_dataclass(self) -> None:
        ctx = DOMContext(heading="Test", paragraph="Description")
        assert ctx.heading == "Test"
        assert ctx.paragraph == "Description"
        assert ctx.list_items == []
