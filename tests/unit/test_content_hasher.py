from app.utilities.content_hasher import (
    compute_content_hash,
    compute_content_item_hash,
    compute_page_content_hash,
    compute_pricing_hash,
    compute_service_hash,
    compute_social_hash,
)


class TestCanonicalizeValue:
    def test_none_returns_null(self):
        result = compute_content_hash(None)
        assert len(result) == 64

    def test_bool_true(self):
        h1 = compute_content_hash(True)
        h2 = compute_content_hash("true")
        assert h1 == h2

    def test_bool_false(self):
        h1 = compute_content_hash(False)
        h2 = compute_content_hash("false")
        assert h1 == h2

    def test_int(self):
        h1 = compute_content_hash(42)
        h2 = compute_content_hash("42")
        assert h1 == h2

    def test_float(self):
        h1 = compute_content_hash(3.14)
        h2 = compute_content_hash("3.14")
        assert h1 == h2

    def test_string_whitespace_normalized(self):
        h1 = compute_content_hash("  hello   world  ")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_string_case_insensitive(self):
        h1 = compute_content_hash("Hello World")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_list(self):
        h1 = compute_content_hash([1, 2, 3])
        h2 = compute_content_hash("[1,2,3]")
        assert h1 == h2

    def test_dict_sorted_keys(self):
        h1 = compute_content_hash({"b": 2, "a": 1})
        h2 = compute_content_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_nested_structures(self):
        h1 = compute_content_hash({"key": [1, 2]})
        h2 = compute_content_hash({"key": [1, 2]})
        assert h1 == h2

    def test_fallback_for_unknown_types(self):
        class Custom:
            def __str__(self):
                return "custom"

        h1 = compute_content_hash(Custom())
        h2 = compute_content_hash("custom")
        assert h1 == h2


class TestComputeContentHash:
    def test_returns_64_char_hex(self):
        result = compute_content_hash("test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        h1 = compute_content_hash("AC Repair", "home-services", 99.99)
        h2 = compute_content_hash("AC Repair", "home-services", 99.99)
        assert h1 == h2

    def test_different_inputs_different_hashes(self):
        h1 = compute_content_hash("Service A")
        h2 = compute_content_hash("Service B")
        assert h1 != h2

    def test_order_matters_for_positional_args(self):
        h1 = compute_content_hash("A", "B")
        h2 = compute_content_hash("B", "A")
        assert h1 != h2

    def test_empty_input(self):
        result = compute_content_hash()
        assert len(result) == 64


class TestComputePageContentHash:
    def test_deterministic(self):
        h1 = compute_page_content_hash("<html>test</html>", "https://example.com")
        h2 = compute_page_content_hash("<html>test</html>", "https://example.com")
        assert h1 == h2

    def test_different_html_different_hash(self):
        h1 = compute_page_content_hash("<html>page1</html>", "https://example.com")
        h2 = compute_page_content_hash("<html>page2</html>", "https://example.com")
        assert h1 != h2


class TestComputeServiceHash:
    def test_basic(self):
        h = compute_service_hash("AC Repair", "home-services", "Fix your AC", 99.99, "USD")
        assert len(h) == 64

    def test_optional_fields_default(self):
        h = compute_service_hash("AC Repair")
        assert len(h) == 64

    def test_none_category_treated_as_empty(self):
        h1 = compute_service_hash("AC Repair", None)
        h2 = compute_service_hash("AC Repair", "")
        assert h1 == h2

    def test_none_price_treated_as_empty(self):
        h1 = compute_service_hash("AC Repair", None, None, None)
        h2 = compute_service_hash("AC Repair", "", "", "")
        assert h1 == h2

    def test_same_service_same_hash(self):
        h1 = compute_service_hash("Cleaning", "residential", "Deep clean", 150.0)
        h2 = compute_service_hash("Cleaning", "residential", "Deep clean", 150.0)
        assert h1 == h2


class TestComputePricingHash:
    def test_basic(self):
        h = compute_pricing_hash("AC Repair", "hvac", 99.99, 79.99, "USD")
        assert len(h) == 64

    def test_optional_fields(self):
        h = compute_pricing_hash("AC Repair")
        assert len(h) == 64

    def test_same_pricing_same_hash(self):
        h1 = compute_pricing_hash("Cleaning", "residential", 150.0, 120.0, "USD")
        h2 = compute_pricing_hash("Cleaning", "residential", 150.0, 120.0, "USD")
        assert h1 == h2

    def test_different_prices_different_hash(self):
        h1 = compute_pricing_hash("Cleaning", "residential", 150.0)
        h2 = compute_pricing_hash("Cleaning", "residential", 200.0)
        assert h1 != h2


class TestComputeContentItemHash:
    def test_basic(self):
        h = compute_content_item_hash("Blog Post", "https://example.com/blog/1", "Author")
        assert len(h) == 64

    def test_optional_fields(self):
        h = compute_content_item_hash("Blog Post", "https://example.com/blog/1")
        assert len(h) == 64

    def test_same_content_same_hash(self):
        h1 = compute_content_item_hash("Title", "https://url", "Author", "2024-01-01", "blog")
        h2 = compute_content_item_hash("Title", "https://url", "Author", "2024-01-01", "blog")
        assert h1 == h2


class TestComputeSocialHash:
    def test_basic(self):
        h = compute_social_hash("linkedin", "https://linkedin.com/company/test", "testcompany")
        assert len(h) == 64

    def test_optional_username(self):
        h = compute_social_hash("twitter", "https://twitter.com/test")
        assert len(h) == 64

    def test_same_social_same_hash(self):
        h1 = compute_social_hash("linkedin", "https://linkedin.com/company/x", "x")
        h2 = compute_social_hash("linkedin", "https://linkedin.com/company/x", "x")
        assert h1 == h2

    def test_different_platform_different_hash(self):
        h1 = compute_social_hash("linkedin", "https://linkedin.com/x")
        h2 = compute_social_hash("twitter", "https://linkedin.com/x")
        assert h1 != h2
