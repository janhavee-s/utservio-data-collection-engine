import time
from typing import Any

from bs4 import BeautifulSoup

from app.parsers.adaptive_orderer import AdaptiveStrategyOrderer
from app.parsers.strategies import (
    GenericCssPatternStrategy,
    GenericDomHeuristicStrategy,
    JsonLdStrategy,
    MetadataStrategy,
    MicrodataStrategy,
    RegexPatternStrategy,
    SchemaOrgStrategy,
    SemanticHtmlStrategy,
)
from app.parsers.strategy import ParsedResult, ParsingStrategy
from app.utilities.performance import cached_parse

DEFAULT_STRATEGIES: list[ParsingStrategy] = [
    JsonLdStrategy(),
    SchemaOrgStrategy(),
    MicrodataStrategy(),
    SemanticHtmlStrategy(),
    GenericDomHeuristicStrategy(),
    GenericCssPatternStrategy(),
    RegexPatternStrategy(),
    MetadataStrategy(),
]


class StrategyParser:
    def __init__(
        self,
        strategies: list[ParsingStrategy] | None = None,
        confidence_threshold: float = 0.8,
        use_adaptive_ordering: bool = True,
    ) -> None:
        self._strategies = strategies or DEFAULT_STRATEGIES
        self._confidence_threshold = confidence_threshold
        self._orderer = AdaptiveStrategyOrderer() if use_adaptive_ordering else None

    @cached_parse(max_size=500, ttl_seconds=1800)
    def parse(self, html: str, url: str) -> ParsedResult:
        soup = BeautifulSoup(html, "html.parser")
        combined = ParsedResult()

        strategies = self._get_ordered_strategies()

        for strategy in strategies:
            start = time.perf_counter()
            try:
                partial = strategy.parse(soup, url)
                elapsed_ms = (time.perf_counter() - start) * 1000
                combined.merge(partial, strategy.name, strategy.weight)

                if self._orderer and partial.confidence > 0:
                    self._orderer.record_success(strategy.name, partial.confidence, elapsed_ms)
                elif self._orderer:
                    self._orderer.record_failure(strategy.name, elapsed_ms)
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if self._orderer:
                    self._orderer.record_failure(strategy.name, elapsed_ms)
                continue

            if combined.confidence >= self._confidence_threshold:
                break

        if self._orderer:
            self._orderer.save_stats()

        return combined

    def _get_ordered_strategies(self) -> list[ParsingStrategy]:
        """Get strategies ordered by historical performance."""
        if not self._orderer:
            return list(self._strategies)

        names = [s.name for s in self._strategies]
        ordered_names = self._orderer.rank_strategies(names)
        name_to_strategy = {s.name: s for s in self._strategies}
        return [name_to_strategy[n] for n in ordered_names if n in name_to_strategy]

    def parse_for_type(self, html: str, url: str, parse_type: str) -> dict[str, Any]:
        result = self.parse(html, url)
        type_map: dict[str, dict[str, Any]] = {
            "company": result.to_company_dict(),
            "services": result.to_service_dict(),
            "pricing": result.to_pricing_dict(),
            "content": result.to_content_dict(),
            "social": result.to_social_dict(),
        }
        output = type_map.get(parse_type, result.to_company_dict())
        output["url"] = url
        return dict(output)
