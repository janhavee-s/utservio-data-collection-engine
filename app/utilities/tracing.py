"""Distributed tracing utilities for trace_id propagation."""
import uuid
from contextvars import ContextVar

import structlog

# Context variable for trace_id propagation
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str:
    """Get current trace_id or generate a new one."""
    tid = trace_id_var.get()
    if not tid:
        tid = str(uuid.uuid4())
        trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: str | None) -> None:
    """Set the current trace_id."""
    trace_id_var.set(trace_id)


def log_with_trace(logger: structlog.stdlib.BoundLogger, event: str, **kwargs: object) -> None:
    """Log an event with the current trace_id."""
    trace_id = get_trace_id()
    logger.bind(trace_id=trace_id).info(event, **kwargs)
