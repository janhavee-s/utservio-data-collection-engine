"""Tests for observability metrics."""

from app.utilities.metrics import MetricsCollector, metrics, time_operation


class TestMetricsCollector:
    def setup_method(self) -> None:
        self.collector = MetricsCollector()

    def test_inc_counter(self) -> None:
        self.collector.inc_counter("test_counter")
        assert self.collector.get_counter_total("test_counter") == 1.0

    def test_inc_counter_with_value(self) -> None:
        self.collector.inc_counter("test_counter", value=5.0)
        assert self.collector.get_counter_total("test_counter") == 5.0

    def test_inc_counter_with_labels(self) -> None:
        self.collector.inc_counter("test_counter", language="en")
        self.collector.inc_counter("test_counter", language="es")
        assert self.collector.get_counter_total("test_counter", language="en") == 1.0
        assert self.collector.get_counter_total("test_counter", language="es") == 1.0

    def test_set_gauge(self) -> None:
        self.collector.set_gauge("queue_size", 42)
        assert self.collector.get_gauge("queue_size") == 42

    def test_observe_histogram(self) -> None:
        for val in [10, 20, 30, 40, 50]:
            self.collector.observe_histogram("test_hist", val)
        stats = self.collector.get_histogram_stats("test_hist")
        assert stats["count"] == 5
        assert stats["avg"] == 30.0
        assert stats["min"] == 10
        assert stats["max"] == 50

    def test_histogram_empty(self) -> None:
        stats = self.collector.get_histogram_stats("empty")
        assert stats["count"] == 0

    def test_render_prometheus(self) -> None:
        self.collector.inc_counter("pages_total")
        output = self.collector.render_prometheus()
        assert "pages_total" in output
        assert "process_uptime_seconds" in output

    def test_get_summary(self) -> None:
        self.collector.inc_counter("pages_total")
        self.collector.set_gauge("queue_size", 5)
        self.collector.observe_histogram("duration", 100)
        summary = self.collector.get_summary()
        assert "counters" in summary
        assert "gauges" in summary
        assert "histograms" in summary


class TestTimeOperation:
    def test_times_operation(self) -> None:
        with time_operation("test_op"):
            pass
        stats = metrics.get_histogram_stats("test_op")
        assert stats["count"] >= 1
