from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deepsupport_os.harness.agent import build_support_agent

router = APIRouter(prefix="/tasks", tags=["tasks"])

# In-memory task registry (checkpoint lives inside agent MemorySaver for now)
_tasks: dict[str, dict[str, Any]] = {}
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_support_agent()
    return _agent


class TaskCreateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None


class TaskCreateResponse(BaseModel):
    task_id: str
    thread_id: str
    status: str
    messages: list[dict[str, Any]] = []
    interrupt: Any = None


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

    messages = []
    for m in result.get("messages", []):
        if hasattr(m, "type") and hasattr(m, "content"):
            messages.append({"role": m.type, "content": str(m.content)[:4000]})
        elif isinstance(m, dict):
            messages.append(m)

    # LangGraph interrupt payload if HITL triggered
    interrupt = None
    try:
        state = agent.get_state(config)
        if state and getattr(state, "tasks", None):
            interrupt = [str(t) for t in state.tasks]
        if state and getattr(state, "next", None):
            interrupt = {"next": list(state.next), "values_keys": list((state.values or {}).keys())}
    except Exception:  # noqa: BLE001
        interrupt = None

    record = {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": "interrupted" if interrupt and getattr(state, "next", None) else "completed",
        "messages": messages,
        "interrupt": interrupt,
    }
    _tasks[task_id] = record
    return TaskCreateResponse(**record)


@router.get("/{task_id}")
def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    return _tasks[task_id]


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool = True
    note: str = ""


@router.post("/resume")
def resume_task(body: ResumeRequest):
    """Resume after human approval (HITL)."""
    agent = get_agent()
    config = {"configurable": {"thread_id": body.thread_id}}
    decision = {"type": "approve" if body.approved else "reject"}
    try:
        # LangGraph HITL resume via Command if available
        from langgraph.types import Command

        result = agent.invoke(Command(resume=decision), config=config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"resume failed: {exc}") from exc

    messages = []
    for m in result.get("messages", []):
        if hasattr(m, "type") and hasattr(m, "content"):
            messages.append({"role": m.type, "content": str(m.content)[:4000]})
    return {
        "thread_id": body.thread_id,
        "approved": body.approved,
        "note": body.note,
        "messages": messages,
    }
