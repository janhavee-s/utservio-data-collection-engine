"""Adaptive Strategy Ordering — dynamically reorders parsing strategies.

Tracks per-strategy statistics:
- Success rate (produced non-empty results)
- Average confidence contribution
- Execution time
- Failure rate

Reorders strategies based on historical performance.
Persists statistics for future crawl runs.
"""

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

STATS_FILE = Path(tempfile.gettempdir()) / "utservio_strategy_stats.json"
SAVE_DEBOUNCE_SECONDS = 60.0


@dataclass
class StrategyStats:
    """Performance statistics for a single parsing strategy."""

    name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_confidence: float = 0.0
    total_time_ms: float = 0.0
    last_updated: str = ""

    @property
    def success_rate(self) -> float:
        """Fraction of runs that produced useful results."""
        if self.total_runs == 0:
            return 0.5
        return self.successful_runs / self.total_runs

    @property
    def average_confidence(self) -> float:
        """Average confidence contribution per successful run."""
        if self.successful_runs == 0:
            return 0.0
        return self.total_confidence / self.successful_runs

    @property
    def average_time_ms(self) -> float:
        """Average execution time in milliseconds."""
        if self.total_runs == 0:
            return 100.0
        return self.total_time_ms / self.total_runs

    @property
    def composite_score(self) -> float:
        """Composite score for ranking. Higher = better."""
        success_weight = 0.5
        confidence_weight = 0.3
        speed_weight = 0.2

        speed_score = max(0.0, 1.0 - (self.average_time_ms / 1000.0))

        return (
            self.success_rate * success_weight
            + self.average_confidence * confidence_weight
            + speed_score * speed_weight
        )

    def record_success(self, confidence: float, time_ms: float) -> None:
        """Record a successful parse."""
        self.total_runs += 1
        self.successful_runs += 1
        self.total_confidence += confidence
        self.total_time_ms += time_ms

    def record_failure(self, time_ms: float) -> None:
        """Record a failed parse."""
        self.total_runs += 1
        self.failed_runs += 1
        self.total_time_ms += time_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "total_confidence": self.total_confidence,
            "total_time_ms": self.total_time_ms,
            "composite_score": self.composite_score,
        }


class AdaptiveStrategyOrderer:
    """Manages adaptive strategy ordering based on historical performance.

    Tracks per-strategy statistics and reorders strategies
    to run the most effective ones first.
    """

    def __init__(
        self, stats_file: Path | None = None, save_debounce: float = SAVE_DEBOUNCE_SECONDS
    ) -> None:
        self._stats_file = stats_file or STATS_FILE
        self._stats: dict[str, StrategyStats] = {}
        self._last_save_time: float = 0.0
        self._save_debounce = save_debounce
        self._load_stats()

    def _load_stats(self) -> None:
        """Load statistics from disk."""
        try:
            if self._stats_file.exists():
                data = json.loads(self._stats_file.read_text())
                for entry in data.get("strategies", []):
                    stats = StrategyStats(
                        name=entry["name"],
                        total_runs=entry.get("total_runs", 0),
                        successful_runs=entry.get("successful_runs", 0),
                        failed_runs=entry.get("failed_runs", 0),
                        total_confidence=entry.get("total_confidence", 0.0),
                        total_time_ms=entry.get("total_time_ms", 0.0),
                    )
                    self._stats[stats.name] = stats
                logger.debug("strategy_stats_loaded", count=len(self._stats))
        except Exception as e:
            logger.warning("strategy_stats_load_failed", error=str(e))

    def save_stats(self) -> None:
        """Persist statistics to disk with debouncing.

        Only writes if at least save_debounce seconds have passed since the last save.
        Call save_stats_force() to bypass the debounce.
        """
        now = time.monotonic()
        if now - self._last_save_time < self._save_debounce:
            return
        self._do_save()

    def save_stats_force(self) -> None:
        """Force persist statistics to disk, bypassing debounce."""
        self._do_save()

    def _do_save(self) -> None:
        """Actually write stats to disk."""
        try:
            data = {"strategies": [s.to_dict() for s in self._stats.values()]}
            self._stats_file.write_text(json.dumps(data, indent=2))
            self._last_save_time = time.monotonic()
            logger.debug("strategy_stats_saved", count=len(self._stats))
        except Exception as e:
            logger.warning("strategy_stats_save_failed", error=str(e))

    def get_stats(self, strategy_name: str) -> StrategyStats:
        """Get or create stats for a strategy."""
        if strategy_name not in self._stats:
            self._stats[strategy_name] = StrategyStats(name=strategy_name)
        return self._stats[strategy_name]

    def record_success(self, strategy_name: str, confidence: float, time_ms: float) -> None:
        """Record a successful parse for a strategy."""
        stats = self.get_stats(strategy_name)
        stats.record_success(confidence, time_ms)

    def record_failure(self, strategy_name: str, time_ms: float) -> None:
        """Record a failed parse for a strategy."""
        stats = self.get_stats(strategy_name)
        stats.record_failure(time_ms)

    def rank_strategies(self, strategy_names: list[str]) -> list[str]:
        """Rank strategies by composite score, highest first.

        Returns strategy names ordered by historical performance.
        Strategies with no history are placed in the middle.
        """
        scored: list[tuple[float, int, str]] = []

        for i, name in enumerate(strategy_names):
            stats = self.get_stats(name)
            scored.append((stats.composite_score, i, name))

        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return [name for _, _, name in scored]

    def get_statistics_summary(self) -> dict[str, Any]:
        """Get summary of all strategy statistics."""
        return {
            name: {
                "success_rate": round(s.success_rate, 3),
                "avg_confidence": round(s.average_confidence, 3),
                "avg_time_ms": round(s.average_time_ms, 1),
                "composite_score": round(s.composite_score, 3),
                "total_runs": s.total_runs,
            }
            for name, s in sorted(
                self._stats.items(), key=lambda x: x[1].composite_score, reverse=True
            )
        }
