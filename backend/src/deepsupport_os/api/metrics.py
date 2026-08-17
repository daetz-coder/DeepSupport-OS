"""Performance metrics API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from deepsupport_os.middleware.metrics import get_metrics, get_metrics_summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def metrics():
    """Get detailed performance metrics."""
    return get_metrics()


@router.get("/summary")
def metrics_summary():
    """Get metrics summary."""
    return get_metrics_summary()
