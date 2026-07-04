from fastapi import APIRouter, Security
from fastapi.responses import PlainTextResponse

from app.api.auth import verify_api_key
from app.utilities.metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    _api_key: str = Security(verify_api_key),
) -> str:
    """Prometheus metrics endpoint.

    Returns all collected metrics in Prometheus exposition format.
    """
    return metrics.render_prometheus()


@router.get("/metrics/summary")
async def metrics_summary(
    _api_key: str = Security(verify_api_key),
) -> dict[str, object]:
    """JSON summary of all metrics."""
    return metrics.get_summary()
