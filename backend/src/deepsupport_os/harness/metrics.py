"""Turn-level metrics written under workspace/{thread_id}/metrics.json."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from deepsupport_os.harness.workspace import ensure_thread_workspace

METRICS_NAME = "metrics.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize_trace(trace: dict[str, Any] | None) -> dict[str, Any]:
    steps = (trace or {}).get("steps") or []
    tool_calls = 0
    tool_errors = 0
    subagents = 0
    for step in steps:
        kind = step.get("kind")
        if kind == "tool_call":
            tool_calls += 1
        elif kind == "tool_result":
            content = str(step.get("content") or "")
            low = content.lower()
            if '"ok": false' in low or '"error"' in low or low.startswith("error"):
                tool_errors += 1
        elif kind == "subagent_dispatch":
            subagents += 1
    return {
        "step_count": len(steps),
        "tool_calls": tool_calls,
        "tool_error_signals": tool_errors,
        "subagent_dispatches": subagents,
        "tool_ok_rate": (
            round((tool_calls - min(tool_errors, tool_calls)) / tool_calls, 3)
            if tool_calls
            else None
        ),
    }


def write_turn_metrics(
    thread_id: str,
    *,
    task_id: str,
    status: str,
    trace: dict[str, Any] | None,
    duration_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = ensure_thread_workspace(thread_id)
    summary = summarize_trace(trace)
    body: dict[str, Any] = {
        "schema_version": 1,
        "thread_id": thread_id,
        "task_id": task_id,
        "status": status,
        "updated_at": _utcnow(),
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        **summary,
    }
    if extra:
        body.update(extra)
    path = root / METRICS_NAME
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return body


class TurnTimer:
    """Simple wall-clock timer for a task turn."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
