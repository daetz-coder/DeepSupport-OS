"""Timeline API endpoints for execution tracking and audit."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from deepsupport_os.harness.execution_timeline import get_all_timelines, get_timeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("")
def list_timelines() -> dict[str, Any]:
    """List all active timelines with summary statistics."""
    return {
        "timelines": get_all_timelines(),
    }


@router.get("/task/{task_id}")
def get_task_timeline(task_id: str) -> dict[str, Any]:
    """Get detailed timeline for a specific task."""
    timelines = get_all_timelines()
    if task_id not in timelines:
        raise HTTPException(status_code=404, detail=f"Timeline not found for task: {task_id}")
    
    return timelines[task_id]


@router.get("/task/{task_id}/events")
def get_task_events(task_id: str) -> list[dict[str, Any]]:
    """Get flat list of events for a task."""
    try:
        timeline = get_timeline(task_id)
        return timeline.get_timeline()
    except Exception as e:
        logger.exception("Failed to get task events")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/task/{task_id}")
def clear_task_timeline(task_id: str) -> dict[str, Any]:
    """Clear timeline for a task (cleanup)."""
    from deepsupport_os.harness.execution_timeline import clear_timeline
    
    clear_timeline(task_id)
    return {"status": "cleared", "task_id": task_id}
