from bs4 import BeautifulSoup

from app.parsers.strategies.generic_css import GenericCssPatternStrategy
from app.parsers.strategies.generic_dom import GenericDomHeuristicStrategy
from app.parsers.strategies.json_ld import JsonLdStrategy
from app.parsers.strategies.metadata import MetadataStrategy
from app.parsers.strategies.microdata import MicrodataStrategy
from app.parsers.strategies.regex_pattern import RegexPatternStrategy
from app.parsers.strategies.schema_org import SchemaOrgStrategy
from app.parsers.strategies.semantic_html import SemanticHtmlStrategy
from app.parsers.strategy import ParsedResult, ParsingStrategy
from app.parsers.strategy_parser import StrategyParser


class TestParsedResult:
    def test_merge_company_name(self) -> None:
        a = ParsedResult()
        b = ParsedResult(company_name="Test Company")
        a.merge(b, "test", 0.3)
        assert a.company_name == "Test Company"
        # Confidence: (1/12 * 0.7) + (0.3 * 0.3) = 0.1483
        assert abs(a.confidence - 0.1483) < 0.01

    def test_merge_does_not_overwrite_with_higher_weight(self) -> None:
        # New behavior: higher weight replaces lower weight
        a = ParsedResult(company_name="Original")
        b = ParsedResult(company_name="New")
        a.merge(b, "test", 0.5)  # Higher weight replaces
        assert a.company_name == "New"

    def test_merge_does_not_overwrite_with_lower_weight(self) -> None:
        # New behavior: lower weight does not replace higher weight
        a = ParsedResult(company_name="Original")
        a._field_weights["company_name"] = 0.8  # Existing has higher weight
        b = ParsedResult(company_name="New")
        a.merge(b, "test", 0.3)  # Lower weight does not replace
        assert a.company_name == "Original"

    def test_merge_services(self) -> None:
        a = ParsedResult()
        b = ParsedResult(services=[{"name": "Service A", "description": "Desc A"}])
        a.merge(b, "test", 0.3)
        assert len(a.services) == 1
        assert a.services[0]["name"] == "Service A"

    def test_merge_services_no_duplicates(self) -> None:
        a = ParsedResult(services=[{"name": "Service A"}])
        b = ParsedResult(services=[{"name": "Service A"}, {"name": "Service B"}])
        a.merge(b, "test", 0.3)
        assert len(a.services) == 2

    def test_merge_social_links(self) -> None:
        a = ParsedResult()
        b = ParsedResult(social_links={"linkedin": "https://linkedin.com/test"})
        a.merge(b, "test", 0.3)
        assert a.social_links["linkedin"] == "https://linkedin.com/test"

    def test_merge_pricing(self) -> None:
        a = ParsedResult()
        b = ParsedResult(pricing=[{"service_name": "Basic", "base_price": 9.99}])
        a.merge(b, "test", 0.3)
        assert len(a.pricing) == 1
        assert a.pricing[0]["service_name"] == "Basic"

    def test_merge_content(self) -> None:
        a = ParsedResult()
        b = ParsedResult(content=[{"title": "Article 1"}])
        a.merge(b, "test", 0.3)
        assert len(a.content) == 1

    def test_merge_social_profiles(self) -> None:
        a = ParsedResult()
        b = ParsedResult(
            social_profiles=[{"platform": "twitter", "profile_url": "https://twitter.com/test"}]
        )
        a.merge(b, "test", 0.3)
        assert len(a.social_profiles) == 1

    def test_merge_confidence_cap(self) -> None:
        a = ParsedResult(confidence=0.9)
        b = ParsedResult(company_name="Test")
        a.merge(b, "test", 0.5)
        # New formula: (1/12 * 0.7) + (0.5 * 0.3) = 0.2083
        assert abs(a.confidence - 0.2083) < 0.01

    def test_to_company_dict(self) -> None:
        result = ParsedResult(
            company_name="Test",
            description="Desc",
            logo="https://logo.png",
            contact_email="test@test.com",
            contact_phone="+1234567890",
            social_links={"linkedin": "https://linkedin.com/test"},
        )
        d = result.to_company_dict()
        assert d["name"] == "Test"
        assert d["description"] == "Desc"
        assert d["logo"] == "https://logo.png"
        assert d["contact_email"] == "test@test.com"

    def test_to_service_dict(self) -> None:
        result = ParsedResult(services=[{"name": "S1"}])
        d = result.to_service_dict()
        assert d["services"] == [{"name": "S1"}]

    def test_to_pricing_dict(self) -> None:
        result = ParsedResult(pricing=[{"service_name": "P1", "base_price": 10}])
        d = result.to_pricing_dict()
        assert d["pricing"][0]["service_name"] == "P1"

    def test_to_content_dict(self) -> None:
        result = ParsedResult(content=[{"title": "T1"}])
        d = result.to_content_dict()
        assert d["content"][0]["title"] == "T1"

    def test_to_social_dict(self) -> None:
        result = ParsedResult(social_profiles=[{"platform": "twitter"}])
        d = result.to_social_dict()
        assert d["social_profiles"][0]["platform"] == "twitter"


class TestJsonLdStrategy:
    def setup_method(self) -> None:
        self.strategy = JsonLdStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "json_ld"
        assert self.strategy.weight == 0.30

    def test_extracts_organization(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "LocalBusiness",
            "name": "Test Company",
            "description": "A test company",
            "logo": "/logo.png",
            "telephone": "+1234567890",
            "email": "info@test.com",
            "address": {
                "addressLocality": "London",
                "addressCountry": "UK"
            },
            "sameAs": ["https://linkedin.com/company/test"]
        }
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "Test Company"
        assert result.description == "A test company"
        assert result.contact_phone == "+1234567890"
        assert result.contact_email == "info@test.com"
        assert result.headquarters == "London, UK"
        assert "linkedin" in result.social_links

    def test_extracts_services(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Service",
            "name": "Cleaning Service",
            "description": "Professional cleaning"
        }
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.services) == 1
        assert result.services[0]["name"] == "Cleaning Service"

    def test_extracts_products_with_pricing(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Basic Plan",
            "offers": {
                "price": "29.99",
                "priceCurrency": "USD"
            }
        }
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.pricing) == 1
        assert result.pricing[0]["base_price"] == 29.99

    def test_extracts_articles(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Article",
            "headline": "Test Article",
            "description": "Article desc",
            "author": {"name": "John"},
            "datePublished": "2024-01-01"
        }
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.content) == 1
        assert result.content[0]["title"] == "Test Article"
        assert result.content[0]["author"] == "John"

    def test_handles_invalid_json(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">invalid json</script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name is None

    def test_handles_empty_html(self) -> None:
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name is None
        assert len(result.services) == 0


class TestSchemaOrgStrategy:
    def setup_method(self) -> None:
        self.strategy = SchemaOrgStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "schema_org"
        assert self.strategy.weight == 0.25

    def test_extracts_organization(self) -> None:
        html = """
        <html><body>
        <div itemscope itemtype="https://schema.org/LocalBusiness">
            <span itemprop="name">Schema Company</span>
            <span itemprop="description">Schema desc</span>
            <span itemprop="telephone">+9876543210</span>
            <span itemprop="email">info@schema.com</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "Schema Company"
        assert result.description == "Schema desc"
        assert result.contact_phone == "+9876543210"
        assert result.contact_email == "info@schema.com"

    def test_extracts_service(self) -> None:
        html = """
        <html><body>
        <div itemscope itemtype="https://schema.org/Service">
            <span itemprop="name">Plumbing</span>
            <span itemprop="description">Pipe repair</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.services) == 1
        assert result.services[0]["name"] == "Plumbing"


class TestMicrodataStrategy:
    def setup_method(self) -> None:
        self.strategy = MicrodataStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "microdata"
        assert self.strategy.weight == 0.15

    def test_extracts_itemprop_name(self) -> None:
        html = """
        <html><body>
        <h1 itemprop="name">My Company</h1>
        <p itemprop="description">About us</p>
        <a itemprop="email" href="mailto:info@my.com">Email</a>
        <a itemprop="telephone" href="tel:+1112223333">Phone</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "My Company"
        assert result.description == "About us"
        assert result.contact_email == "info@my.com"
        assert result.contact_phone == "+1112223333"

    def test_extracts_prices(self) -> None:
        html = """
        <html><body>
        <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">Bathroom Cleaning</span>
            <span itemprop="price" content="49.99">₹49.99</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.pricing) >= 1
        assert result.pricing[0]["service_name"] == "Bathroom Cleaning"


class TestSemanticHtmlStrategy:
    def setup_method(self) -> None:
        self.strategy = SemanticHtmlStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "semantic_html"
        assert self.strategy.weight == 0.15

    def test_extracts_from_header(self) -> None:
        html = """
        <html><body>
        <header>
            <h1>Semantic Company</h1>
            <img src="/logo.png">
        </header>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "Semantic Company"

    def test_extracts_services_from_headings(self) -> None:
        html = """
        <html><body>
        <main>
            <h2>Our Services</h2>
            <h3>Cleaning Service</h3>
            <p>Professional home cleaning</p>
            <h3>Repair Service</h3>
            <p>Expert repairs</p>
        </main>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.services) >= 1

    def test_extracts_articles(self) -> None:
        html = """
        <html><body>
        <article>
            <h2>Blog Post</h2>
            <p>Summary text</p>
            <a href="/blog/post1">Read more</a>
        </article>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.content) >= 1
        assert result.content[0]["title"] == "Blog Post"

    def test_extracts_from_footer(self) -> None:
        html = """
        <html><body>
        <footer>
            <a href="mailto:footer@test.com">Email</a>
            <a href="tel:+1234567890">Phone</a>
        </footer>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.contact_email == "footer@test.com"
        assert result.contact_phone == "+1234567890"

    def test_extracts_social_links(self) -> None:
        html = """
        <html><body>
        <a href="https://linkedin.com/company/test">LinkedIn</a>
        <a href="https://facebook.com/test">Facebook</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert "linkedin" in result.social_links
        assert "facebook" in result.social_links


class TestGenericDomHeuristicStrategy:
    def setup_method(self) -> None:
        self.strategy = GenericDomHeuristicStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "generic_dom_heuristic"
        assert self.strategy.weight == 0.10

    def test_extracts_h1_as_name(self) -> None:
        html = """
        <html><body>
        <h1>Heuristic Company</h1>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "Heuristic Company"

    def test_extracts_prices_from_elements(self) -> None:
        html = """
        <html><body>
        <h1>AC Service</h1>
        <div class="price-card">
            <span class="price">$49.99</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "AC Service"

    def test_extracts_email_and_phone(self) -> None:
        html = """
        <html><body>
        <a href="mailto:info@heuristic.com">Email</a>
        <a href="tel:+1112223333">Phone</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.contact_email == "info@heuristic.com"
        assert result.contact_phone == "+1112223333"


class TestGenericCssPatternStrategy:
    def setup_method(self) -> None:
        self.strategy = GenericCssPatternStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "generic_css_pattern"
        assert self.strategy.weight == 0.10

    def test_extracts_services_by_class(self) -> None:
        html = """
        <html><body>
        <div class="service-card">
            <h3>AC Repair</h3>
            <p>Fix your air conditioner</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.services) >= 1
        assert result.services[0]["name"] == "AC Repair"

    def test_extracts_pricing_by_class(self) -> None:
        html = """
        <html><body>
        <div class="pricing-card">
            <h4>Basic Plan</h4>
            <span class="price-amount">$29.99</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.pricing) >= 1

    def test_extracts_content_by_class(self) -> None:
        html = """
        <html><body>
        <div class="blog-post">
            <h3>New Blog</h3>
            <p>Summary</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert len(result.content) >= 1


class TestRegexPatternStrategy:
    def setup_method(self) -> None:
        self.strategy = RegexPatternStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "regex_pattern"
        assert self.strategy.weight == 0.05

    def test_extracts_email(self) -> None:
        html = "<html><body><p>Contact us at info@example.com</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.contact_email == "info@example.com"

    def test_extracts_phone(self) -> None:
        html = "<html><body><p>Call us at +1-234-567-8900</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.contact_phone is not None

    def test_extracts_prices(self) -> None:
        html = "<html><body><p>Starting at $49.99 per month</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        # Regex strategy no longer extracts anonymous prices (no placeholder entries)
        assert len(result.pricing) == 0

    def test_extracts_social_links(self) -> None:
        html = '<html><body><a href="https://linkedin.com/company/test">LinkedIn</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert "linkedin" in result.social_links

    def test_ignores_image_extensions(self) -> None:
        html = "<html><body><p>image@example.png</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.contact_email is None


class TestMetadataStrategy:
    def setup_method(self) -> None:
        self.strategy = MetadataStrategy()

    def test_name_and_weight(self) -> None:
        assert self.strategy.name == "metadata"
        assert self.strategy.weight == 0.10

    def test_extracts_og_tags(self) -> None:
        html = """
        <html><head>
        <meta property="og:site_name" content="Meta Company">
        <meta property="og:description" content="Meta description">
        <meta property="og:image" content="/meta-logo.png">
        <meta property="og:url" content="https://linkedin.com/company/test">
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.company_name == "Meta Company"
        assert result.description == "Meta description"
        assert result.logo == "https://example.com/meta-logo.png"
        assert "linkedin" in result.social_links

    def test_extracts_twitter_tags(self) -> None:
        html = """
        <html><head>
        <meta name="twitter:site" content="@testcompany">
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert "twitter" in result.social_links

    def test_extracts_meta_description(self) -> None:
        html = """
        <html><head>
        <meta name="description" content="Meta desc fallback">
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.description == "Meta desc fallback"

    def test_extracts_favicon(self) -> None:
        html = """
        <html><head>
        <link rel="icon" href="/favicon.ico">
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.strategy.parse(soup, "https://example.com")
        assert result.logo == "https://example.com/favicon.ico"


class TestStrategyParser:
    def setup_method(self) -> None:
        self.parser = StrategyParser(use_adaptive_ordering=False)

    def test_parses_empty_html(self) -> None:
        result = self.parser.parse("<html><body></body></html>", "https://example.com")
        assert isinstance(result, ParsedResult)

    def test_parses_json_ld(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "LocalBusiness",
            "name": "Strategy Company",
            "description": "Desc",
            "telephone": "+1234567890"
        }
        </script>
        </head><body></body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert result.company_name == "Strategy Company"
        assert result.description == "Desc"
        assert result.contact_phone == "+1234567890"

    def test_confidence_threshold_stops_early(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "LocalBusiness",
            "name": "Fast Company"
        }
        </script>
        </head><body></body></html>
        """
        parser = StrategyParser(confidence_threshold=0.3, use_adaptive_ordering=False)
        result = parser.parse(html, "https://example.com")
        assert result.company_name == "Fast Company"

    def test_parse_for_type_company(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "LocalBusiness", "name": "Test"}
        </script>
        </head><body></body></html>
        """
        result = self.parser.parse_for_type(html, "https://example.com", "company")
        assert result["name"] == "Test"
        assert result["url"] == "https://example.com"

    def test_parse_for_type_services(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Service", "name": "Cleaning"}
        </script>
        </head><body></body></html>
        """
        result = self.parser.parse_for_type(html, "https://example.com", "services")
        assert len(result["services"]) >= 1

    def test_parse_for_type_pricing(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Plan", "offers": {"price": "29.99"}}
        </script>
        </head><body></body></html>
        """
        result = self.parser.parse_for_type(html, "https://example.com", "pricing")
        assert len(result["pricing"]) >= 1

    def test_parse_for_type_content(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "Blog Post"}
        </script>
        </head><body></body></html>
        """
        result = self.parser.parse_for_type(html, "https://example.com", "content")
        assert len(result["content"]) >= 1

    def test_parse_for_type_social(self) -> None:
        html = """
        <html><body>
        <a href="https://linkedin.com/company/testcompany">LinkedIn</a>
        <a href="https://facebook.com/testcompany">Facebook</a>
        </body></html>
        """
        result = self.parser.parse_for_type(html, "https://example.com", "social")
        assert len(result["social_profiles"]) >= 1

    def test_custom_strategies(self) -> None:
        class DummyStrategy(ParsingStrategy):
            @property
            def name(self) -> str:
                return "dummy"

            @property
            def weight(self) -> float:
                return 1.0

            def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
                return ParsedResult(company_name="Dummy Co")

        parser = StrategyParser(strategies=[DummyStrategy()])
        result = parser.parse("<html></html>", "https://example.com")
        assert result.company_name == "Dummy Co"

    def test_strategy_exception_handled(self) -> None:
        class BadStrategy(ParsingStrategy):
            @property
            def name(self) -> str:
                return "bad"

            @property
            def weight(self) -> float:
                return 0.5

            def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
                raise ValueError("boom")

        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "LocalBusiness", "name": "Good Co"}
        </script>
        </head><body></body></html>
        """
        parser = StrategyParser(strategies=[BadStrategy(), JsonLdStrategy()])
        result = parser.parse(html, "https://example.com")
        assert result.company_name == "Good Co"

    def test_merges_multiple_strategies(self) -> None:
        html = """
        <html><head>
        <meta property="og:site_name" content="Meta Name">
        <meta name="description" content="Meta description">
        <script type="application/ld+json">
        {"@type": "LocalBusiness", "name": "LD Name", "telephone": "+1234567890"}
        </script>
        </head><body>
        <h1>HTML Name</h1>
        <a href="mailto:info@test.com">Email</a>
        </body></html>
        """
        result = self.parser.parse(html, "https://example.com")
        assert result.company_name is not None
        assert result.confidence > 0
        assert len(result.strategy_results) > 0
