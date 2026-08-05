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
from deepsupport_os.harness.run_overview import build_run_overview
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


def _slim_interrupt(interrupt: Any) -> Any:
    """Drop bulky PregelTask reprs from SSE/API interrupt payloads."""
    if not isinstance(interrupt, dict):
        return interrupt
    slim = dict(interrupt)
    tasks = slim.get("tasks") or []
    slim["tasks"] = [str(t)[:120] for t in tasks[:5]]
    return slim


def _sse_done_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Compact done event — full audit/trace.steps bloat breaks SSE clients."""
    interrupt = _slim_interrupt(record.get("interrupt"))
    trace = record.get("trace") if isinstance(record.get("trace"), dict) else {}
    overview = record.get("overview") if isinstance(record.get("overview"), dict) else {}
    slim_overview = {
        k: overview.get(k)
        for k in (
            "status",
            "duration_ms",
            "scope",
            "plan",
            "agents",
            "skills",
            "mcp",
            "tools",
            "step_count",
            "thread_step_count",
        )
        if k in overview
    }
    # Stages without nested step bodies (UI already has live steps)
    stages = []
    for st in overview.get("stages") or []:
        if not isinstance(st, dict):
            continue
        stages.append(
            {
                "id": st.get("id"),
                "label": st.get("label"),
                "status": st.get("status"),
                "step_count": st.get("step_count"),
                "tool_count": st.get("tool_count"),
                "summary": st.get("summary"),
            }
        )
    slim_overview["stages"] = stages
    slim_steps: list[dict[str, Any]] = []
    for step in trace.get("steps") or []:
        if not isinstance(step, dict):
            continue
        item = dict(step)
        content = item.get("content")
        if isinstance(content, str) and len(content) > 1200:
            item["content"] = content[:1200] + "…"
        slim_steps.append(item)
    return {
        "task_id": record.get("task_id"),
        "thread_id": record.get("thread_id"),
        "status": record.get("status"),
        "workspace_path": record.get("workspace_path"),
        "messages": record.get("messages") or [],
        "interrupt": interrupt,
        "todos": record.get("todos") or [],
        "overview": slim_overview,
        "applied_writes": record.get("applied_writes") or [],
        "artifacts": record.get("artifacts") or [],
        "manifest": record.get("manifest"),
        "metrics": record.get("metrics"),
        "memory_paths": record.get("memory_paths") or [],
        "trace": {
            "steps": slim_steps,
            "skills_used": list(trace.get("skills_used") or []),
            "stages": stages,
        },
    }


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
    overview = build_run_overview(
        list(trace.get("steps") or []),
        todos=todos,
        metrics={"duration_ms": duration_ms},
        status=status,
    )
    manifest = write_manifest(thread_id, task_id=task_id, status=status)
    metrics = write_turn_metrics(
        thread_id,
        task_id=task_id,
        status=status,
        trace=trace,
        duration_ms=duration_ms,
        extra={
            "skills_used": overview.get("skills") or [],
            "agents_used": overview.get("agents") or [],
            "mcp": overview.get("mcp") or {},
            "stage_count": len(overview.get("stages") or []),
        },
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
        "overview": overview,
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
    overview: dict[str, Any] = {}
    applied_writes: list[dict[str, Any]] = []
    todos: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    memory_paths: list[str] = []


@router.get("")
def list_tasks(limit: int = 50):
    return {"items": task_store.list_tasks(limit=limit)}


@router.get("/threads")
def list_threads(limit: int = 40):
    """Conversation sidebar: threads with nested runs."""
    return {"items": task_store.list_threads(limit=limit)}


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
    answer: str | None = None
    interrupt_type: str | None = None  # "ask" | "hitl"
    task_id: str | None = None


@router.post("/resume")
def resume_task(body: ResumeRequest):
    """Resume after ask_user answer or HITL write approval."""
    agent = get_agent(body.thread_id)
    config = {"configurable": {"thread_id": body.thread_id}}
    ws = ensure_thread_workspace(body.thread_id)
    timer = TurnTimer()

    pre_state = agent.get_state(config)
    pre_messages = (getattr(pre_state, "values", None) or {}).get("messages") or []
    interrupt_before = extract_interrupt_info(agent, config) or {}
    itype = (body.interrupt_type or interrupt_before.get("type") or "hitl").strip().lower()

    applied: list[dict[str, Any]] = []
    if itype == "ask":
        answer = (body.answer if body.answer is not None else body.note) or ""
        if not str(answer).strip():
            raise HTTPException(status_code=400, detail="answer required for ask resume")
        resume_payload: Any = str(answer).strip()
    else:
        pending = collect_pending_writes(
            pre_messages,
            pending=interrupt_before.get("pending_writes"),
        )
        if body.approved and pending:
            applied = apply_approved_writes(pending, task_id=body.task_id or body.thread_id)
        resume_payload = {"decisions": [{"type": "approve" if body.approved else "reject"}]}

    try:
        from langgraph.types import Command

        result = agent.invoke(Command(resume=resume_payload), config=config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"resume failed: {exc}") from exc

    messages = result.get("messages", [])
    interrupt = extract_interrupt_info(agent, config)
    if interrupt:
        status = "interrupted"
    elif itype == "ask":
        status = "completed"
    else:
        status = "approved" if body.approved else "rejected"
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
        "approved": body.approved if itype != "ask" else True,
        "note": body.note,
        "answer": body.answer,
        "interrupt_type": itype,
    }


@router.get("/meta/audit")
def get_audit(limit: int = 50, task_id: str | None = None):
    return {"items": list_audit(limit=limit, task_id=task_id)}


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


@router.post("/stream")
async def stream_task(body: TaskCreateRequest):
    """SSE: status / token / tool / message / interrupt / done."""
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
            for item in agent.stream(
                {"messages": [{"role": "user", "content": body.message}]},
                config=config,
                stream_mode=["updates", "messages"],
            ):
                mode = "updates"
                chunk: Any = item
                if isinstance(item, tuple) and len(item) == 2 and item[0] in {"updates", "messages"}:
                    mode, chunk = item[0], item[1]

                if mode == "messages":
                    msg_chunk = chunk[0] if isinstance(chunk, tuple) and chunk else chunk
                    name = type(msg_chunk).__name__
                    msg_type = str(getattr(msg_chunk, "type", "") or "")
                    # Only stream assistant token deltas (skip human/tool noise)
                    is_ai = "AI" in name or msg_type in {"ai", "AIMessageChunk"}
                    if not is_ai:
                        continue
                    text = _message_text(getattr(msg_chunk, "content", None))
                    if text:
                        yield {
                            "event": "token",
                            "data": json.dumps({"text": text}, ensure_ascii=False),
                        }
                    continue

                if not isinstance(chunk, dict):
                    continue
                # Interrupt surface as a synthetic updates chunk
                if "__interrupt__" in chunk:
                    continue
                for _node, update in chunk.items():
                    if _node == "__interrupt__":
                        continue
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
        except Exception as exc:  # noqa: BLE001
            # Still try to surface interrupt if the run paused for ask/HITL
            interrupt_on_err = extract_interrupt_info(agent, config)
            if interrupt_on_err:
                yield {
                    "event": "interrupt",
                    "data": json.dumps(
                        _slim_interrupt(interrupt_on_err), ensure_ascii=False, default=str
                    ),
                }
            else:
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
                "data": json.dumps(_slim_interrupt(interrupt), ensure_ascii=False, default=str),
            }

        try:
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
                "data": json.dumps(_sse_done_payload(record), ensure_ascii=False, default=str),
            }
        except Exception as exc:  # noqa: BLE001
            # Interrupt already yielded above when present; still close the stream cleanly
            if not interrupt:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
                }
            else:
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "task_id": task_id,
                            "thread_id": thread_id,
                            "status": "interrupted",
                            "interrupt": _slim_interrupt(interrupt),
                            "workspace_path": str(ws),
                            "messages": serialize_messages(final_messages),
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                }

    return EventSourceResponse(event_gen())
