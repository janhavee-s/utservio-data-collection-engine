"""Tests for intelligent page classification."""

from app.parsers.page_classifier import PageClassifier, PageType


class TestPageClassifier:
    def setup_method(self) -> None:
        self.classifier = PageClassifier()

    def test_classifies_homepage_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/")
        assert result.page_type == PageType.HOMEPAGE
        assert result.confidence > 0.5

    def test_classifies_services_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/services")
        assert result.page_type == PageType.SERVICE
        assert result.confidence > 0.5

    def test_classifies_pricing_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/pricing")
        assert result.page_type == PageType.PRICING
        assert result.confidence > 0.5

    def test_classifies_blog_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/blog")
        assert result.page_type == PageType.BLOG
        assert result.confidence > 0.5

    def test_classifies_faq_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/faq")
        assert result.page_type == PageType.FAQ

    def test_classifies_contact_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/contact")
        assert result.page_type == PageType.CONTACT

    def test_classifies_about_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/about")
        assert result.page_type == PageType.ABOUT

    def test_classifies_legal_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/privacy")
        assert result.page_type == PageType.LEGAL

    def test_classifies_career_by_url(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/careers")
        assert result.page_type == PageType.CAREER

    def test_classifies_by_heading(self) -> None:
        html = """
        <html><head><title>Pricing</title></head>
        <body><h1>Our Pricing Plans</h1></body></html>
        """
        result = self.classifier.classify(html, "https://example.com/other")
        assert result.page_type == PageType.PRICING

    def test_classifies_by_schema(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">{"@type": "FAQPage"}</script>
        </head><body></body></html>
        """
        result = self.classifier.classify(html, "https://example.com/other")
        assert result.page_type == PageType.FAQ

    def test_multiple_signals_increase_confidence(self) -> None:
        html = """
        <html lang="en"><head><title>About Us</title></head>
        <body><h1>About Us</h1></body></html>
        """
        result = self.classifier.classify(html, "https://example.com/about")
        assert result.page_type == PageType.ABOUT
        assert len(result.signals_used) >= 2

    def test_unknown_page_type(self) -> None:
        result = self.classifier.classify("<html></html>", "https://example.com/xyz123")
        assert result.page_type in (PageType.UNKNOWN, PageType.HOMEPAGE)

    def test_classification_result_dataclass(self) -> None:
        result = PageClassifier().classify(
            "<html><h1>Services</h1></html>", "https://example.com/services"
        )
        assert result.page_type is not None
        assert result.confidence >= 0
        assert isinstance(result.signals_used, list)
