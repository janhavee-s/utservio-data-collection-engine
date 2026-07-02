"""Crawl Budget Engine — controls crawling scope and priority.

Implements:
- Maximum pages per competitor
- Maximum crawl depth
- Priority queue with scoring
- URL relevance ranking
- Budget tracking and enforcement
"""

import heapq
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import structlog

from app.configuration.settings import get_settings

logger = structlog.get_logger(__name__)

PRIORITY_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "high": [
        (r"/(service|pricing|plan|product|feature|solution)", 15),
        (r"/(about|company|team|story|mission)", 12),
    ],
    "medium": [
        (r"/(blog|article|news|resource|case-study|post)", 10),
        (r"/(contact|support|help|faq)", 8),
        (r"/(testimonial|review|case)", 7),
    ],
    "low": [
        (r"/(privacy|terms|legal|policy|cookie)", 3),
        (r"/(career|job|hiring|recruit)", 2),
        (r"/(sitemap|feed|rss)", 1),
    ],
}

SOURCE_SCORES: dict[str, int] = {
    "nav": 10,
    "sitemap": 8,
    "robots": 6,
    "footer": 5,
    "meta": 3,
    "internal_link": 2,
}


@dataclass
class CrawlCandidate:
    """A URL candidate with priority score for the crawl queue.

    Higher priority = crawled first.
    """

    priority: int = field(compare=False)
    url: str = field(compare=False)
    depth: int = field(compare=False, default=0)
    source: str = field(compare=False, default="internal_link")
    context: str = field(compare=False, default="")

    def __lt__(self, other: "CrawlCandidate") -> bool:
        return self.priority > other.priority


class CrawlBudgetEngine:
    """Controls crawling scope and priority for a single competitor.

    Enforces:
    - Maximum pages per crawl run
    - Maximum link depth from homepage
    - Priority-based URL selection
    - Deduplication of visited URLs

    Configuration (via DiscoverySettings):
    - max_pages_per_competitor: hard cap on pages
    - max_depth: maximum hops from homepage
    """

    def __init__(self) -> None:
        self._settings = get_settings().discovery
        self._visited: set[str] = set()
        self._queue: list[CrawlCandidate] = []
        self._pages_crawled = 0
        self._pages_skipped = 0
        self._depth_exceeded = 0
        self._budget_exceeded = 0

    def reset(self) -> None:
        """Reset budget state for a new crawl run."""
        self._visited.clear()
        self._queue.clear()
        self._pages_crawled = 0
        self._pages_skipped = 0
        self._depth_exceeded = 0
        self._budget_exceeded = 0

    def add_url(
        self,
        url: str,
        *,
        depth: int = 0,
        source: str = "internal_link",
        context: str = "",
    ) -> bool:
        """Add a URL to the crawl queue if within budget.

        Returns True if URL was accepted, False if rejected.
        """
        normalized = url.rstrip("/")

        if normalized in self._visited:
            return False

        if depth > self._settings.max_depth:
            self._depth_exceeded += 1
            logger.debug(
                "budget_depth_exceeded",
                url=url,
                depth=depth,
                max_depth=self._settings.max_depth,
            )
            return False

        if self._pages_crawled >= self._settings.max_pages_per_competitor:
            self._budget_exceeded += 1
            logger.debug(
                "budget_max_pages_reached",
                url=url,
                pages_crawled=self._pages_crawled,
                max_pages=self._settings.max_pages_per_competitor,
            )
            return False

        priority = self._score_url(url, depth, source)
        candidate = CrawlCandidate(
            priority=priority,
            url=url,
            depth=depth,
            source=source,
            context=context,
        )
        heapq.heappush(self._queue, candidate)
        self._visited.add(normalized)
        return True

    def next(self) -> CrawlCandidate | None:
        """Get the next highest-priority URL from the queue."""
        if not self._queue:
            return None
        candidate = heapq.heappop(self._queue)
        self._pages_crawled += 1
        return candidate

    def _score_url(self, url: str, depth: int, source: str) -> int:
        """Score a URL based on multiple ranking signals."""
        score = 0
        url_lower = url.lower()

        source_score = SOURCE_SCORES.get(source, 0)
        score += source_score

        for _level, patterns in PRIORITY_SIGNALS.items():
            for pattern, weight in patterns:
                if re.search(pattern, url_lower):
                    score += weight
                    break

        depth_penalty = depth * 3
        score -= depth_penalty

        path_parts = [p for p in urlparse(url).path.split("/") if p]
        if len(path_parts) <= 2:
            score += 3

        if depth == 0:
            score += 5

        return score

    def add_urls_batch(
        self,
        urls: list[dict[str, Any]],
    ) -> int:
        """Add multiple URLs to the queue. Returns count accepted."""
        accepted = 0
        for item in urls:
            if self.add_url(
                item["url"],
                depth=item.get("depth", 0),
                source=item.get("source", "internal_link"),
                context=item.get("context", ""),
            ):
                accepted += 1
        return accepted

    @property
    def remaining_budget(self) -> int:
        """Number of pages remaining in budget."""
        return max(0, self._settings.max_pages_per_competitor - self._pages_crawled)

    @property
    def has_budget(self) -> bool:
        """Whether there is remaining crawl budget."""
        return self.remaining_budget > 0 and bool(self._queue)

    @property
    def stats(self) -> dict[str, Any]:
        """Return budget statistics."""
        return {
            "pages_crawled": self._pages_crawled,
            "pages_skipped": self._pages_skipped,
            "depth_exceeded": self._depth_exceeded,
            "budget_exceeded": self._budget_exceeded,
            "queue_size": len(self._queue),
            "visited_count": len(self._visited),
            "remaining_budget": self.remaining_budget,
        }

    def get_prioritized_urls(self, limit: int | None = None) -> list[CrawlCandidate]:
        """Get all queued URLs sorted by priority without consuming them."""
        sorted_queue = sorted(self._queue, key=lambda c: c.priority, reverse=True)
        if limit:
            return sorted_queue[:limit]
        return sorted_queue
