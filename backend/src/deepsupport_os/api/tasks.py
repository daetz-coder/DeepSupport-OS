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
from deepsupport_os.harness.agent import MEMORY_PATHS, build_support_agent
from deepsupport_os.harness.artifacts import list_artifacts, read_artifact, write_manifest
from deepsupport_os.harness.hitl_apply import apply_approved_writes, collect_pending_writes
from deepsupport_os.harness.metrics import TurnTimer, write_turn_metrics
from deepsupport_os.harness.state_extract import extract_todos
from deepsupport_os.harness.workspace import ensure_thread_workspace

router = APIRouter(prefix="/tasks", tags=["tasks"])

# One compiled agent per thread so system prompt workspace path stays correct.
_agents: dict[str, Any] = {}
_MAX_CACHED_AGENTS = 48


def get_agent(thread_id: str | None = None):
    """Per-thread agent: prompt embeds `/workspace/<thread_id>/` for that session."""
    tid = (thread_id or "").strip() or "default"
    agent = _agents.get(tid)
    if agent is not None:
        return agent
    if len(_agents) >= _MAX_CACHED_AGENTS:
        # Drop an arbitrary oldest entry (dict preserves insertion order).
        _agents.pop(next(iter(_agents)), None)
    agent = build_support_agent(thread_id=tid, use_daytona=True)
    _agents[tid] = agent
    return agent


def reset_agents() -> None:
    """Drop cached agents (e.g. after Skills/MCP config changes)."""
    _agents.clear()


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
    todos: list[dict[str, Any]] | None = None,
    agent: Any = None,
    config: dict | None = None,
    result: dict | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    trace = build_trace(messages, interrupt=interrupt, audit=_recent_audit(20))
    ws = workspace_path or str(ensure_thread_workspace(thread_id))
    if todos is None and agent is not None and config is not None:
        todos = extract_todos(agent, config, result=result)
    todos = todos or []
    manifest = write_manifest(thread_id, task_id=task_id, status=status)
    metrics = write_turn_metrics(
        thread_id,
        task_id=task_id,
        status=status,
        trace=trace,
        duration_ms=duration_ms,
    )
    artifacts = list_artifacts(thread_id)
    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": status,
        "workspace_path": ws,
        "messages": serialize_messages(messages),
        "interrupt": interrupt,
        "trace": trace,
        "applied_writes": applied or [],
        "todos": todos,
        "artifacts": artifacts,
        "manifest": manifest,
        "metrics": metrics,
        "memory_paths": list(MEMORY_PATHS),
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
    todos: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    memory_paths: list[str] = []


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
    timer = TurnTimer()

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
        agent=agent,
        config=config,
        result=result if isinstance(result, dict) else None,
        duration_ms=timer.ms(),
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


@router.get("/{task_id}/artifacts")
def get_task_artifacts(task_id: str):
    record = task_store.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    thread_id = record["thread_id"]
    return {"task_id": task_id, "thread_id": thread_id, "items": list_artifacts(thread_id)}


@router.get("/{task_id}/artifacts/{path:path}")
def get_task_artifact_content(task_id: str, path: str):
    record = task_store.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    data = read_artifact(record["thread_id"], path)
    if not data.get("ok"):
        raise HTTPException(status_code=404, detail=data.get("error") or "not found")
    return data


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
    timer = TurnTimer()

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
        agent=agent,
        config=config,
        result=result if isinstance(result, dict) else None,
        duration_ms=timer.ms(),
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
    timer = TurnTimer()

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
        last_todos: list[dict[str, Any]] = []
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
                    if isinstance(update, dict) and "todos" in update:
                        todos_update = extract_todos(
                            agent, config, result=update if isinstance(update, dict) else None
                        )
                        if todos_update != last_todos:
                            last_todos = todos_update
                            yield {
                                "event": "todos",
                                "data": json.dumps(
                                    {"todos": todos_update},
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            }
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
                                elif kind == "context_offload":
                                    yield {
                                        "event": "context_offload",
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
            agent=agent,
            config=config,
            duration_ms=timer.ms(),
        )
        if record.get("todos") and record["todos"] != last_todos:
            yield {
                "event": "todos",
                "data": json.dumps({"todos": record["todos"]}, ensure_ascii=False, default=str),
            }
        _persist(record)
        yield {
            "event": "done",
            "data": json.dumps(record, ensure_ascii=False, default=str),
        }

    return EventSourceResponse(event_gen())
