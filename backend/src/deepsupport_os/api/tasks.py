from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from deepsupport_os.api.trace import build_trace, extract_interrupt_info, serialize_messages
from deepsupport_os.db import task_store
from deepsupport_os.db.repositories import list_audit
from deepsupport_os.harness.agent import build_support_agent
from deepsupport_os.harness.hitl_apply import apply_approved_writes, collect_pending_writes
from deepsupport_os.harness.workspace import ensure_thread_workspace

router = APIRouter(prefix="/tasks", tags=["tasks"])

_agent = None


def get_agent(thread_id: str | None = None):
    """Shared hybrid agent: local Skills/workspace + optional Daytona /sandbox/ sidecar."""
    global _agent
    if _agent is None:
        _agent = build_support_agent(thread_id=thread_id, use_daytona=True)
    return _agent


def _recent_audit(limit: int = 30) -> list[dict[str, Any]]:
    return list_audit(limit=limit)


def _build_record(
    *,
    task_id: str,
    thread_id: str,
    messages: list[Any],
    interrupt: Any,
    status: str,
    applied: list[dict] | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    trace = build_trace(messages, interrupt=interrupt, audit=_recent_audit(20))
    ws = workspace_path or str(ensure_thread_workspace(thread_id))
    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": status,
        "workspace_path": ws,
        "messages": serialize_messages(messages),
        "interrupt": interrupt,
        "trace": trace,
        "applied_writes": applied or [],
    }


def _persist(record: dict[str, Any]) -> None:
    task_store.save_task(record)


class TaskCreateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None


class TaskCreateResponse(BaseModel):
    task_id: str
    thread_id: str
    status: str
    workspace_path: str | None = None
    messages: list[dict[str, Any]] = []
    interrupt: Any = None
    trace: dict[str, Any] = {}
    applied_writes: list[dict[str, Any]] = []


@router.get("")
def list_tasks(limit: int = 50):
    return {"items": task_store.list_tasks(limit=limit)}


@router.post("", response_model=TaskCreateResponse)
def create_task(body: TaskCreateRequest):
    """Run one support turn via Deep Agents Harness."""
    thread_id = body.thread_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    ws = ensure_thread_workspace(thread_id)
    agent = get_agent(thread_id)
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
        workspace_path=str(ws),
    )
    _persist(record)
    return TaskCreateResponse(**record)


@router.get("/{task_id}")
def get_task(task_id: str):
    record = task_store.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    return record


@router.get("/{task_id}/trace")
def get_task_trace(task_id: str):
    record = task_store.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    return record.get("trace") or build_trace([], interrupt=record.get("interrupt"))


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool = True
    note: str = ""
    task_id: str | None = None


@router.post("/resume")
def resume_task(body: ResumeRequest):
    """Resume after human approval (HITL) and apply approved writes."""
    agent = get_agent(body.thread_id)
    config = {"configurable": {"thread_id": body.thread_id}}
    ws = ensure_thread_workspace(body.thread_id)

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
        workspace_path=str(ws),
    )
    _persist(record)
    return {
        **record,
        "approved": body.approved,
        "note": body.note,
    }


@router.get("/meta/audit")
def get_audit(limit: int = 50, task_id: str | None = None):
    return {"items": list_audit(limit=limit, task_id=task_id)}


@router.post("/stream")
async def stream_task(body: TaskCreateRequest):
    """SSE stream of agent progress: status / tool / message / interrupt / done."""
    thread_id = body.thread_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    ws = ensure_thread_workspace(thread_id)
    agent = get_agent(thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    def event_gen() -> Iterator[dict[str, str]]:
        yield {
            "event": "status",
            "data": json.dumps(
                {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "status": "running",
                    "workspace_path": str(ws),
                },
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
                if not isinstance(chunk, dict):
                    continue
                for node, update in chunk.items():
                    payload: dict[str, Any] = {"node": node}
                    if isinstance(update, dict) and "messages" in update:
                        msgs = update.get("messages") or []
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
                                elif kind == "subagent_dispatch":
                                    yield {
                                        "event": "subagent",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                                elif kind == "tool_result":
                                    yield {
                                        "event": "tool_end",
                                        "data": json.dumps(step, ensure_ascii=False, default=str),
                                    }
                                elif kind in {"assistant", "user"}:
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
            workspace_path=str(ws),
        )
        _persist(record)
        yield {
            "event": "done",
            "data": json.dumps(record, ensure_ascii=False, default=str),
        }

    return EventSourceResponse(event_gen())
