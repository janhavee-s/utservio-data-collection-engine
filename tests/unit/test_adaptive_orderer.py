"""Tests for adaptive strategy ordering."""

import tempfile
from pathlib import Path

from app.parsers.adaptive_orderer import AdaptiveStrategyOrderer, StrategyStats


class TestStrategyStats:
    def test_initial_state(self) -> None:
        stats = StrategyStats(name="test")
        assert stats.total_runs == 0
        assert stats.success_rate == 0.5
        assert stats.average_confidence == 0.0

    def test_record_success(self) -> None:
        stats = StrategyStats(name="test")
        stats.record_success(confidence=0.8, time_ms=50.0)
        assert stats.total_runs == 1
        assert stats.successful_runs == 1
        assert stats.success_rate == 1.0
        assert stats.average_confidence == 0.8

    def test_record_failure(self) -> None:
        stats = StrategyStats(name="test")
        stats.record_failure(time_ms=100.0)
        assert stats.total_runs == 1
        assert stats.failed_runs == 1
        assert stats.success_rate == 0.0

    def test_composite_score(self) -> None:
        stats = StrategyStats(name="test")
        stats.record_success(confidence=0.9, time_ms=30.0)
        score = stats.composite_score
        assert score > 0.5

    def test_to_dict(self) -> None:
        stats = StrategyStats(name="test")
        stats.record_success(confidence=0.8, time_ms=50.0)
        d = stats.to_dict()
        assert d["name"] == "test"
        assert d["total_runs"] == 1


class TestAdaptiveStrategyOrderer:
    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.stats_file = Path(self.tmpdir) / "stats.json"
        self.orderer = AdaptiveStrategyOrderer(stats_file=self.stats_file)

    def test_rank_strategies_default_order(self) -> None:
        names = ["json_ld", "schema_org", "microdata", "semantic_html"]
        ranked = self.orderer.rank_strategies(names)
        assert set(ranked) == set(names)

    def test_rank_strategies_after_success(self) -> None:
        for _ in range(10):
            self.orderer.record_success("json_ld", confidence=0.9, time_ms=20.0)
            self.orderer.record_failure("schema_org", time_ms=100.0)

        names = ["json_ld", "schema_org", "microdata"]
        ranked = self.orderer.rank_strategies(names)
        assert ranked[0] == "json_ld"

    def test_persistence(self) -> None:
        self.orderer.record_success("json_ld", confidence=0.9, time_ms=20.0)
        self.orderer.save_stats()

        new_orderer = AdaptiveStrategyOrderer(stats_file=self.stats_file)
        stats = new_orderer.get_stats("json_ld")
        assert stats.total_runs == 1
        assert stats.successful_runs == 1

    def test_get_statistics_summary(self) -> None:
        self.orderer.record_success("json_ld", confidence=0.9, time_ms=20.0)
        self.orderer.record_success("schema_org", confidence=0.7, time_ms=40.0)
        summary = self.orderer.get_statistics_summary()
        assert "json_ld" in summary
        assert "schema_org" in summary

    def test_empty_stats_returns_default_order(self) -> None:
        names = ["a", "b", "c"]
        ranked = self.orderer.rank_strategies(names)
        assert ranked == ["a", "b", "c"]
