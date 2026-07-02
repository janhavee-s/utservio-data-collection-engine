"""Tests for Crawl Budget Engine."""

from app.collectors.crawl_budget import CrawlBudgetEngine


class TestCrawlBudgetEngine:
    def setup_method(self) -> None:
        self.engine = CrawlBudgetEngine()

    def test_add_url_within_budget(self) -> None:
        result = self.engine.add_url("https://example.com/services", depth=0, source="nav")
        assert result is True
        assert self.engine.has_budget

    def test_add_url_duplicate_rejected(self) -> None:
        self.engine.add_url("https://example.com/page")
        result = self.engine.add_url("https://example.com/page")
        assert result is False

    def test_add_url_depth_exceeded(self) -> None:
        result = self.engine.add_url(
            "https://example.com/deep/page",
            depth=10,
        )
        assert result is False

    def test_next_returns_highest_priority(self) -> None:
        self.engine.add_url("https://example.com/privacy", source="internal_link")
        self.engine.add_url("https://example.com/services", source="nav")
        self.engine.add_url("https://example.com/pricing", source="sitemap")

        first = self.engine.next()
        assert first is not None
        assert "pricing" in first.url or "services" in first.url

    def test_next_returns_none_when_empty(self) -> None:
        assert self.engine.next() is None

    def test_stats(self) -> None:
        self.engine.add_url("https://example.com/a")
        self.engine.add_url("https://example.com/b")
        self.engine.next()
        stats = self.engine.stats
        assert stats["pages_crawled"] == 1
        assert stats["visited_count"] == 2

    def test_remaining_budget(self) -> None:
        self.engine.add_url("https://example.com/a")
        self.engine.next()
        remaining = self.engine.remaining_budget
        assert remaining >= 0

    def test_add_urls_batch(self) -> None:
        urls = [
            {"url": "https://example.com/a", "depth": 0, "source": "nav"},
            {"url": "https://example.com/b", "depth": 1, "source": "footer"},
            {"url": "https://example.com/c", "depth": 0, "source": "sitemap"},
        ]
        accepted = self.engine.add_urls_batch(urls)
        assert accepted == 3

    def test_reset(self) -> None:
        self.engine.add_url("https://example.com/a")
        self.engine.reset()
        assert self.engine.stats["pages_crawled"] == 0
        assert self.engine.stats["visited_count"] == 0

    def test_get_prioritized_urls(self) -> None:
        self.engine.add_url("https://example.com/privacy", source="internal_link")
        self.engine.add_url("https://example.com/services", source="nav")
        prioritized = self.engine.get_prioritized_urls()
        assert len(prioritized) == 2
        assert prioritized[0].priority >= prioritized[1].priority

    def test_scoring_services_beats_privacy(self) -> None:
        self.engine.add_url("https://example.com/privacy", depth=0, source="internal_link")
        self.engine.add_url("https://example.com/services", depth=0, source="nav")
        prioritized = self.engine.get_prioritized_urls()
        assert prioritized[0].url == "https://example.com/services"
