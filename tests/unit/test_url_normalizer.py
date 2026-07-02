from app.utilities.url_normalizer import normalize_content_url, normalize_url


class TestNormalizeUrl:
    def test_empty_string(self):
        assert normalize_url("") == ""

    def test_lowercase_scheme(self):
        result = normalize_url("HTTPS://Example.com/Page")
        assert result.startswith("https://")

    def test_lowercase_host(self):
        result = normalize_url("https://EXAMPLE.COM/page")
        assert "example.com" in result

    def test_strip_www_prefix(self):
        result = normalize_url("https://www.example.com/page")
        assert "www." not in result

    def test_strip_http_default_port(self):
        result = normalize_url("http://example.com:80/page")
        assert ":80" not in result

    def test_strip_https_default_port(self):
        result = normalize_url("https://example.com:443/page")
        assert ":443" not in result

    def test_keep_non_default_port(self):
        result = normalize_url("https://example.com:8080/page")
        assert ":8080" in result

    def test_strip_trailing_slash(self):
        result = normalize_url("https://example.com/page/")
        assert not result.endswith("/")

    def test_keep_root_slash(self):
        result = normalize_url("https://example.com/")
        assert result.endswith("/")

    def test_strip_fragment(self):
        result = normalize_url("https://example.com/page#section")
        assert "#" not in result

    def test_strip_tracking_params(self):
        result = normalize_url("https://example.com/page?utm_source=google&utm_medium=cpc&id=123")
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=123" in result

    def test_strip_fbclid(self):
        result = normalize_url("https://example.com/page?fbclid=abc123&name=test")
        assert "fbclid" not in result
        assert "name=test" in result

    def test_strip_gclid(self):
        result = normalize_url("https://example.com/page?gclid=abc123&name=test")
        assert "gclid" not in result

    def test_sort_query_params(self):
        result = normalize_url("https://example.com/page?z=1&a=2&m=3")
        assert "a=2" in result
        assert "m=3" in result
        assert "z=1" in result
        a_pos = result.index("a=2")
        m_pos = result.index("m=3")
        z_pos = result.index("z=1")
        assert a_pos < m_pos < z_pos

    def test_relative_url_with_base(self):
        result = normalize_url("/about", base_url="https://example.com")
        assert result == "https://example.com/about"

    def test_relative_url_without_base(self):
        result = normalize_url("/about")
        assert result == "/about"

    def test_already_normalized(self):
        url = "https://example.com/page"
        result = normalize_url(url)
        assert result == url

    def test_ref_param_stripped(self):
        result = normalize_url("https://example.com/page?ref=homepage&id=1")
        assert "ref=" not in result
        assert "id=1" in result

    def test_source_param_stripped(self):
        result = normalize_url("https://example.com/page?source=newsletter&id=1")
        assert "source=" not in result


class TestNormalizeContentUrl:
    def test_strips_trailing_slash(self):
        result = normalize_content_url("https://example.com/blog/post/")
        assert not result.endswith("/")

    def test_keeps_non_slash_url(self):
        result = normalize_content_url("https://example.com/blog/post")
        assert result == "https://example.com/blog/post"

    def test_root_strips_trailing_slash_for_dedup(self):
        result = normalize_content_url("https://example.com/")
        assert result == "https://example.com"

    def test_with_base_url(self):
        result = normalize_content_url("/blog/post", base_url="https://example.com")
        assert result == "https://example.com/blog/post"

    def test_empty_string(self):
        assert normalize_content_url("") == ""
