"""Observability — Prometheus metrics for the crawling engine.

Exposes metrics for:
- Pages discovered, crawled, skipped
- Cache hits and misses
- Playwright fallbacks
- Strategy success/failure
- Crawl, parse, and discovery durations
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetricValue:
    """A single metric value with labels."""

    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Collects and stores Prometheus-compatible metrics.

    Thread-safe metric collection for concurrent crawling operations.
    Supports counters, gauges, and histograms.
    """

    MAX_COUNTER_ENTRIES = 10000
    MAX_HISTOGRAM_ENTRIES = 10000

    def __init__(self) -> None:
        self._counters: dict[str, list[MetricValue]] = defaultdict(list)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._start_time = time.time()

    def inc_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Increment a counter metric."""
        self._counters[name].append(MetricValue(value=value, labels=labels))
        if len(self._counters[name]) > self.MAX_COUNTER_ENTRIES:
            self._counters[name] = self._counters[name][-self.MAX_COUNTER_ENTRIES :]

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge metric."""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        self._gauges[key] = value
        if len(self._gauges) > self.MAX_COUNTER_ENTRIES:
            keys = list(self._gauges.keys())
            for k in keys[: len(keys) // 2]:
                del self._gauges[k]

    def observe_histogram(self, name: str, value: float, **labels: str) -> None:
        """Record a histogram observation."""
        self._histograms[name].append(value)
        if len(self._histograms[name]) > self.MAX_HISTOGRAM_ENTRIES:
            self._histograms[name] = self._histograms[name][-self.MAX_HISTOGRAM_ENTRIES :]

    def get_counter_total(self, name: str, **labels: str) -> float:
        """Get total value of a counter."""
        total = 0.0
        for mv in self._counters.get(name, []):
            if not labels or all(mv.labels.get(k) == v for k, v in labels.items()):
                total += mv.value
        return total

    def get_gauge(self, name: str, **labels: str) -> float | None:
        """Get gauge value."""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        return self._gauges.get(key)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics."""
        values = self._histograms.get(name, [])
        if not values:
            return {
                "count": 0.0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        return {
            "count": count,
            "sum": sum(sorted_vals),
            "avg": sum(sorted_vals) / count,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[count // 2],
            "p95": sorted_vals[int(count * 0.95)] if count > 20 else sorted_vals[-1],
            "p99": sorted_vals[int(count * 0.99)] if count > 100 else sorted_vals[-1],
        }

    def render_prometheus(self) -> str:
        """Render all metrics in Prometheus exposition format."""
        lines: list[str] = []
        lines.append("# Utservio Competitor Intelligence Engine Metrics")
        lines.append("")

        for name, values in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            label_totals: dict[str, float] = defaultdict(float)
            for mv in values:
                label_key = ",".join(f'{k}="{v}"' for k, v in sorted(mv.labels.items()))
                label_totals[label_key] += mv.value
            for label_key, total in label_totals.items():
                suffix = f"{{{label_key}}}" if label_key else ""
                lines.append(f"{name}{suffix} {total}")
            lines.append("")

        for key, value in self._gauges.items():
            parts = key.rsplit(":", 1)
            name = parts[0]
            label_str = parts[1] if len(parts) > 1 else ""
            lines.append(f"# TYPE {name} gauge")
            suffix = f"{{{label_str}}}" if label_str else ""
            lines.append(f"{name}{suffix} {value}")
            lines.append("")

        for name, values in self._histograms.items():  # type: ignore[assignment]
            values_: list[float] = values  # type: ignore[assignment]
            if not values_:
                continue
            stats = self.get_histogram_stats(name)
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_sum {stats['sum']}")
            for bucket_name in ["min", "p50", "p95", "p99", "max"]:
                lines.append(f"{name}_{bucket_name} {stats[bucket_name]}")
            lines.append("")

        uptime = time.time() - self._start_time
        lines.append("# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {uptime:.2f}")
        lines.append("")

        return "\n".join(lines)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        summary: dict[str, Any] = {
            "counters": {},
            "gauges": dict(self._gauges),
            "histograms": {},
        }

        for name, values in self._counters.items():
            total = sum(mv.value for mv in values)
            summary["counters"][name] = total

        for name in self._histograms:
            summary["histograms"][name] = self.get_histogram_stats(name)

        return summary


metrics = MetricsCollector()


def time_operation(name: str, **labels: str) -> Any:
    """Context manager to time an operation and record to histogram."""
    return _TimerContext(metrics, name, labels)


class _TimerContext:
    def __init__(self, collector: MetricsCollector, name: str, labels: dict[str, str]) -> None:
        self._collector = collector
        self._name = name
        self._labels = labels
        self._start: float = 0

    def __enter__(self) -> "_TimerContext":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._collector.observe_histogram(self._name, elapsed_ms, **self._labels)
