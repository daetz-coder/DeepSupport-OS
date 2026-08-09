from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from deepsupport_os.api.trace import build_trace, extract_interrupt_info, serialize_messages
from deepsupport_os.db import task_store
from deepsupport_os.db.repositories import list_audit
from deepsupport_os.harness.agent import build_support_agent
from deepsupport_os.harness.artifacts import list_artifacts, read_artifact, write_manifest
from deepsupport_os.harness.hitl_runtime import (
    hitl_notice_text as _hitl_notice_text,
    hitl_resume_decisions as _hitl_resume_decisions,
    inject_hitl_notice as _inject_hitl_notice,
    prepare_resume,
)
from deepsupport_os.harness.memory_files import memory_paths_for_thread
from deepsupport_os.harness.metrics import TurnTimer, write_turn_metrics
from deepsupport_os.harness.run_overview import build_run_overview
from deepsupport_os.harness.state_extract import extract_todos
from deepsupport_os.harness.workspace import ensure_thread_workspace

router = APIRouter(prefix="/tasks", tags=["tasks"])

logger = logging.getLogger(__name__)

# One compiled agent per thread so system prompt workspace path stays correct.
_agents: dict[str, Any] = {}
_agents_lock = threading.Lock()
_MAX_CACHED_AGENTS = 48


def get_agent(thread_id: str | None = None):
    """Per-thread agent: prompt embeds `/workspace/<thread_id>/` for that session.

    Locked so concurrent requests for the same thread cannot build two agents in
    parallel and race the shared checkpointer / backend caches.
    """
    tid = (thread_id or "").strip() or "default"
    with _agents_lock:
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
    from deepsupport_os.harness.daytona_backend import clear_thread_backends

    with _agents_lock:
        _agents.clear()
    clear_thread_backends()


def _recent_audit(limit: int = 30, thread_id: str | None = None) -> list[dict[str, Any]]:
    return list_audit(limit=limit, thread_id=thread_id)


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
            "thread_duration_ms",
            "run_count",
            "run_step_count",
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
    trace = build_trace(
        messages, interrupt=interrupt, audit=_recent_audit(20, thread_id=thread_id)
    )
    ws = workspace_path or str(ensure_thread_workspace(thread_id))
    if todos is None and agent is not None and config is not None:
        todos = extract_todos(agent, config, result=result)
    todos = todos or []
    steps = list(trace.get("steps") or [])
    run_overview = build_run_overview(
        steps,
        todos=todos,
        metrics={"duration_ms": duration_ms},
        status=status,
        current_run_only=True,
    )
    thread_overview = build_run_overview(
        steps,
        todos=todos,
        metrics={"duration_ms": duration_ms},
        status=status,
        current_run_only=False,
    )
    prior_ms = task_store.sum_thread_duration_ms(thread_id, exclude_task_id=task_id)
    run_count = max(1, task_store.count_thread_runs(thread_id))
    # If this task_id is new, count_thread_runs won't include it yet
    if task_store.get_task(task_id) is None:
        run_count = task_store.count_thread_runs(thread_id) + 1
    overview = {
        **thread_overview,
        # Chat stage fold stays on the current turn
        "stages": run_overview.get("stages") or [],
        "run_step_count": run_overview.get("step_count") or 0,
        "duration_ms": duration_ms,
        "thread_duration_ms": prior_ms + float(duration_ms or 0),
        "run_count": run_count,
        "scope": "full_thread",
    }
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
            "thread_duration_ms": overview.get("thread_duration_ms"),
            "run_count": overview.get("run_count"),
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
        "memory_paths": memory_paths_for_thread(thread_id),
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


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: str):
    """Purge a conversation: runs, agent cache, workspace, session memory, checkpoint."""
    tid = (thread_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="thread_id required")
    deleted = task_store.delete_thread(tid)
    with _agents_lock:
        _agents.pop(tid, None)
    checkpoint_purged = False
    try:
        import shutil

        from deepsupport_os.core.config import get_settings
        from deepsupport_os.harness.agent import purge_thread_checkpoint
        from deepsupport_os.harness.daytona_backend import clear_thread_backends
        from deepsupport_os.harness.workspace import sanitize_thread_id

        clear_thread_backends(tid)
        checkpoint_purged = purge_thread_checkpoint(tid)
        ws = ensure_thread_workspace(tid)
        if ws.exists() and ws.is_dir():
            shutil.rmtree(ws, ignore_errors=True)
        mem_session = (
            get_settings().resolve("memory") / "threads" / sanitize_thread_id(tid)
        )
        if mem_session.exists() and mem_session.is_dir():
            shutil.rmtree(mem_session, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "thread_id": tid,
        "deleted_runs": deleted,
        "checkpoint_purged": checkpoint_purged,
    }


@router.post("", response_model=TaskCreateResponse)
def create_task(body: TaskCreateRequest):
    """Run one support turn via Deep Agents Harness."""
    from deepsupport_os.harness.runtime_context import run_context

    thread_id = body.thread_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    ws = ensure_thread_workspace(thread_id)
    agent = get_agent(thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    timer = TurnTimer()

    try:
        with run_context(thread_id=thread_id, task_id=task_id):
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
    """Resume after ask_user answer or HITL write approval (sync). Prefer /resume/stream for UI."""
    from langgraph.types import Command

    from deepsupport_os.harness.runtime_context import run_context

    ws = ensure_thread_workspace(body.thread_id)
    timer = TurnTimer()
    task_id = body.task_id or str(uuid.uuid4())
    resume_payload, applied, fallback, itype, agent, config, interrupt_before = _prepare_resume(
        body
    )

    try:
        with run_context(thread_id=body.thread_id, task_id=task_id):
            result = agent.invoke(Command(resume=resume_payload), config=config)
            if itype == "hitl":
                _inject_hitl_notice(agent, config, interrupt_before, body.approved)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"resume failed: {exc}") from exc

    messages = result.get("messages", [])
    interrupt = extract_interrupt_info(agent, config)
    status = "interrupted" if interrupt else fallback
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
def get_audit(
    limit: int = 50, task_id: str | None = None, thread_id: str | None = None
):
    return {"items": list_audit(limit=limit, task_id=task_id, thread_id=thread_id)}


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


def _iter_agent_sse(
    *,
    agent: Any,
    config: dict,
    stream_input: Any,
    task_id: str,
    thread_id: str,
    workspace_path: str,
    timer: TurnTimer,
    applied: list[dict[str, Any]] | None = None,
    fallback_status: str = "completed",
    hitl_notice: tuple[dict[str, Any], bool] | None = None,
) -> Iterator[dict[str, str]]:
    """Shared SSE loop for new turns and ask/HITL resume.

    Re-bind run context after every yield: EventSourceResponse advances the
    sync generator via anyio.to_thread.run_sync, so each next() may run in a
    fresh Context where prior ContextVar tokens are invalid / invisible.
    """
    from deepsupport_os.harness.runtime_context import set_run_context

    def _bind() -> None:
        set_run_context(thread_id=thread_id, task_id=task_id)

    _bind()
    for event in _iter_agent_sse_body(
        agent=agent,
        config=config,
        stream_input=stream_input,
        task_id=task_id,
        thread_id=thread_id,
        workspace_path=workspace_path,
        timer=timer,
        applied=applied,
        fallback_status=fallback_status,
        hitl_notice=hitl_notice,
    ):
        yield event
        _bind()


def _iter_agent_sse_body(
    *,
    agent: Any,
    config: dict,
    stream_input: Any,
    task_id: str,
    thread_id: str,
    workspace_path: str,
    timer: TurnTimer,
    applied: list[dict[str, Any]] | None = None,
    fallback_status: str = "completed",
    hitl_notice: tuple[dict[str, Any], bool] | None = None,
) -> Iterator[dict[str, str]]:
    from deepsupport_os.api.sse_framing import SseSequencer

    seq = SseSequencer(run_id=task_id, thread_id=thread_id)
    yield seq.event(
        "status",
        {
            "task_id": task_id,
            "thread_id": thread_id,
            "status": "running",
            "workspace_path": workspace_path,
        },
    )
    final_messages: list[Any] = []
    last_todos: list[dict[str, Any]] = []
    interrupt: Any = None
    interrupt_emitted = False
    try:
        for item in agent.stream(
            stream_input,
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
                is_ai = "AI" in name or msg_type in {"ai", "AIMessageChunk"}
                if not is_ai:
                    continue
                text = _message_text(getattr(msg_chunk, "content", None))
                if text:
                    yield seq.event("token", {"text": text})
                continue

            if not isinstance(chunk, dict):
                continue
            # Emit interrupt as soon as LangGraph signals it (do not wait for done).
            if "__interrupt__" in chunk or any(k == "__interrupt__" for k in chunk):
                info = extract_interrupt_info(agent, config)
                if info and not interrupt_emitted:
                    interrupt = info
                    interrupt_emitted = True
                    yield seq.event("interrupt", _slim_interrupt(info))
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
                        yield seq.event("todos", {"todos": todos_update})
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
                                yield seq.event("tool_start", step)
                            elif kind == "subagent_dispatch":
                                yield seq.event("subagent", step)
                            elif kind == "context_offload":
                                yield seq.event("context_offload", step)
                            elif kind == "tool_result":
                                yield seq.event("tool_end", step)
                            elif kind in {"assistant", "user"}:
                                yield seq.event("message", step)
    except Exception as exc:  # noqa: BLE001
        interrupt_on_err = extract_interrupt_info(agent, config)
        if interrupt_on_err:
            interrupt = interrupt_on_err
            if not interrupt_emitted:
                interrupt_emitted = True
                yield seq.event("interrupt", _slim_interrupt(interrupt_on_err))
        else:
            yield seq.event("error", {"error": str(exc)})
            return

    if hitl_notice is not None:
        _inject_hitl_notice(agent, config, hitl_notice[0], hitl_notice[1])

    try:
        state = agent.get_state(config)
        state_msgs = (getattr(state, "values", None) or {}).get("messages") or []
        if state_msgs:
            final_messages = state_msgs
    except Exception:  # noqa: BLE001
        pass

    interrupt = extract_interrupt_info(agent, config) or interrupt
    status = "interrupted" if interrupt else fallback_status
    if interrupt and not interrupt_emitted:
        yield seq.event("interrupt", _slim_interrupt(interrupt))

    try:
        record = _build_record(
            task_id=task_id,
            thread_id=thread_id,
            messages=final_messages,
            interrupt=interrupt,
            status=status,
            applied=applied,
            workspace_path=workspace_path,
            agent=agent,
            config=config,
            duration_ms=timer.ms(),
        )
        if record.get("todos") and record["todos"] != last_todos:
            yield seq.event("todos", {"todos": record["todos"]})
        _persist(record)
        yield seq.event("done", _sse_done_payload(record))
    except Exception as exc:  # noqa: BLE001
        if not interrupt:
            yield seq.event("error", {"error": str(exc)})
        else:
            yield seq.event(
                "done",
                {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "status": "interrupted",
                    "interrupt": _slim_interrupt(interrupt),
                    "workspace_path": workspace_path,
                    "messages": serialize_messages(final_messages),
                },
            )


def _prepare_resume(
    body: ResumeRequest,
) -> tuple[Any, list[dict[str, Any]], str, str, Any, dict, dict[str, Any]]:
    """API adapter around harness.hitl_runtime.prepare_resume."""

    def _drop(tid: str) -> None:
        with _agents_lock:
            _agents.pop(tid, None)

    return prepare_resume(
        body,
        get_agent=get_agent,
        extract_interrupt=extract_interrupt_info,
        drop_cached_agent=_drop,
    )


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
        yield from _iter_agent_sse(
            agent=agent,
            config=config,
            stream_input={"messages": [{"role": "user", "content": body.message}]},
            task_id=task_id,
            thread_id=thread_id,
            workspace_path=str(ws),
            timer=timer,
        )

    return EventSourceResponse(event_gen())


@router.post("/resume/stream")
async def resume_task_stream(body: ResumeRequest):
    """SSE resume after ask_user / HITL — same event contract as /stream."""
    from langgraph.types import Command

    ws = ensure_thread_workspace(body.thread_id)
    timer = TurnTimer()
    resume_payload, applied, fallback, itype, agent, config, interrupt_before = _prepare_resume(
        body
    )
    task_id = body.task_id or str(uuid.uuid4())

    def event_gen() -> Iterator[dict[str, str]]:
        yield from _iter_agent_sse(
            agent=agent,
            config=config,
            stream_input=Command(resume=resume_payload),
            task_id=task_id,
            thread_id=body.thread_id,
            workspace_path=str(ws),
            timer=timer,
            applied=applied,
            fallback_status=fallback,
            hitl_notice=(interrupt_before, body.approved) if itype == "hitl" else None,
        )

    return EventSourceResponse(event_gen())
