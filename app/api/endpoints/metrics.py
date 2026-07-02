from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.utilities.metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint.

    Returns all collected metrics in Prometheus exposition format.
    """
    return metrics.render_prometheus()


@router.get("/metrics/summary")
async def metrics_summary() -> dict[str, object]:
    """JSON summary of all metrics."""
    return metrics.get_summary()
