from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sse_starlette.sse import EventSourceResponse

from deepsupport_os.api.trace import build_trace, extract_interrupt_info, serialize_messages
from deepsupport_os.db.models import AuditLog, get_session_factory
from deepsupport_os.harness.agent import build_support_agent
from deepsupport_os.harness.hitl_apply import apply_approved_writes, collect_pending_writes

router = APIRouter(prefix="/tasks", tags=["tasks"])

_tasks: dict[str, dict[str, Any]] = {}
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_support_agent()
    return _agent


def _recent_audit(limit: int = 30) -> list[dict[str, Any]]:
    Session = get_session_factory()
    with Session() as s:
        rows = s.scalars(select(AuditLog).order_by(desc(AuditLog.id)).limit(limit)).all()
        return [
            {
                "id": r.id,
                "task_id": r.task_id,
                "tool": r.tool,
                "arguments": r.arguments,
                "result": r.result[:500] if r.result else "",
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in reversed(rows)
        ]


def _build_record(
    *,
    task_id: str,
    thread_id: str,
    messages: list[Any],
    interrupt: Any,
    status: str,
    applied: list[dict] | None = None,
) -> dict[str, Any]:
    trace = build_trace(messages, interrupt=interrupt, audit=_recent_audit(20))
    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": status,
        "messages": serialize_messages(messages),
        "interrupt": interrupt,
        "trace": trace,
        "applied_writes": applied or [],
    }


class TaskCreateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None


class TaskCreateResponse(BaseModel):
    task_id: str
    thread_id: str
    status: str
    messages: list[dict[str, Any]] = []
    interrupt: Any = None
    trace: dict[str, Any] = {}
    applied_writes: list[dict[str, Any]] = []


@router.post("", response_model=TaskCreateResponse)
def create_task(body: TaskCreateRequest):
    """Run one support turn via Deep Agents Harness."""
    agent = get_agent()
    thread_id = body.thread_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    messages = result.get("messages", [])
    interrupt = extract_interrupt_info(agent, config)
    status = "interrupted" if interrupt else "completed"
    record = _build_record(
        task_id=task_id,
        thread_id=thread_id,
        messages=messages,
        interrupt=interrupt,
        status=status,
    )
    _tasks[task_id] = record
    _tasks[f"thread:{thread_id}"] = record
    return TaskCreateResponse(**record)


@router.get("/{task_id}")
def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    return _tasks[task_id]


@router.get("/{task_id}/trace")
def get_task_trace(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    record = _tasks[task_id]
    return record.get("trace") or build_trace([], interrupt=record.get("interrupt"))


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool = True
    note: str = ""
    task_id: str | None = None


@router.post("/resume")
def resume_task(body: ResumeRequest):
    """Resume after human approval (HITL) and apply approved writes."""
    agent = get_agent()
    config = {"configurable": {"thread_id": body.thread_id}}

    # Capture pending writes before resume clears interrupt
    pre_state = agent.get_state(config)
    pre_messages = (getattr(pre_state, "values", None) or {}).get("messages") or []
    interrupt_before = extract_interrupt_info(agent, config) or {}
    pending = collect_pending_writes(
        pre_messages,
        pending=interrupt_before.get("pending_writes"),
    )

    applied: list[dict[str, Any]] = []
    if body.approved and pending:
        applied = apply_approved_writes(pending, task_id=body.task_id or body.thread_id)

    decision = {"decisions": [{"type": "approve" if body.approved else "reject"}]}
    try:
        from langgraph.types import Command

        result = agent.invoke(Command(resume=decision), config=config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"resume failed: {exc}") from exc

    messages = result.get("messages", [])
    interrupt = extract_interrupt_info(agent, config)
    status = "interrupted" if interrupt else ("approved" if body.approved else "rejected")
    task_id = body.task_id or str(uuid.uuid4())
    record = _build_record(
        task_id=task_id,
        thread_id=body.thread_id,
        messages=messages,
        interrupt=interrupt,
        status=status,
        applied=applied,
    )
    _tasks[task_id] = record
    _tasks[f"thread:{body.thread_id}"] = record
    return {
        **record,
        "approved": body.approved,
        "note": body.note,
    }


@router.post("/stream")
async def stream_task(body: TaskCreateRequest):
    """SSE stream of agent progress: status / tool / message / interrupt / done."""
    agent = get_agent()
    thread_id = body.thread_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    def event_gen() -> Iterator[dict[str, str]]:
        yield {
            "event": "status",
            "data": json.dumps(
                {"task_id": task_id, "thread_id": thread_id, "status": "running"},
                ensure_ascii=False,
            ),
        }
        final_messages: list[Any] = []
        try:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": body.message}]},
                config=config,
                stream_mode="updates",
            ):
                # chunk is dict[node_name -> update]
                if not isinstance(chunk, dict):
                    continue
                for node, update in chunk.items():
                    payload: dict[str, Any] = {"node": node}
                    if isinstance(update, dict) and "messages" in update:
                        msgs = update.get("messages") or []
                        # LangGraph may wrap as (action, message) tuples
                        normalized = []
                        for m in msgs:
                            if isinstance(m, tuple) and len(m) == 2:
                                normalized.append(m[1])
                            else:
                                normalized.append(m)
                        if normalized:
                            final_messages.extend(normalized)
                            step_trace = build_trace(normalized)
                            for step in step_trace.get("steps") or []:
                                kind = step.get("kind")
                                if kind == "tool_call":
                                    yield {
                                        "event": "tool_start",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                                elif kind == "tool_result":
                                    yield {
                                        "event": "tool_end",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                                elif kind == "assistant":
                                    yield {
                                        "event": "message",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                                elif kind == "user":
                                    yield {
                                        "event": "message",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                    else:
                        payload["update"] = str(update)[:500]
                        yield {
                            "event": "status",
                            "data": json.dumps(payload, ensure_ascii=False, default=str),
                        }
        except Exception as exc:  # noqa: BLE001
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            }
            return

        # Prefer full state messages if available
        try:
            state = agent.get_state(config)
            state_msgs = (getattr(state, "values", None) or {}).get("messages") or []
            if state_msgs:
                final_messages = state_msgs
        except Exception:  # noqa: BLE001
            pass

        interrupt = extract_interrupt_info(agent, config)
        status = "interrupted" if interrupt else "completed"
        if interrupt:
            yield {
                "event": "interrupt",
                "data": json.dumps(interrupt, ensure_ascii=False, default=str),
            }

        record = _build_record(
            task_id=task_id,
            thread_id=thread_id,
            messages=final_messages,
            interrupt=interrupt,
            status=status,
        )
        _tasks[task_id] = record
        _tasks[f"thread:{thread_id}"] = record
        yield {
            "event": "done",
            "data": json.dumps(record, ensure_ascii=False, default=str),
        }

    return EventSourceResponse(event_gen())
