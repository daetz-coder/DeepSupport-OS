"""Build structured execution traces from LangChain / LangGraph messages."""

from __future__ import annotations

import json
from typing import Any


def _clip(text: Any, limit: int = 2000) -> str:
    s = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _tool_calls_from_message(msg: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    raw = getattr(msg, "tool_calls", None) or []
    for tc in raw:
        if isinstance(tc, dict):
            name = tc.get("name") or tc.get("function", {}).get("name")
            args = tc.get("args") or tc.get("function", {}).get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            calls.append(
                {
                    "id": tc.get("id"),
                    "name": name,
                    "args": args,
                }
            )
        else:
            calls.append(
                {
                    "id": getattr(tc, "id", None),
                    "name": getattr(tc, "name", None),
                    "args": getattr(tc, "args", {}),
                }
            )
    # OpenAI-style additional_kwargs
    if not calls:
        ak = getattr(msg, "additional_kwargs", None) or {}
        for tc in ak.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or "{}"
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            calls.append({"id": tc.get("id"), "name": fn.get("name"), "args": args})
    return calls


def serialize_messages(messages: list[Any], *, content_limit: int = 4000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        role = getattr(m, "type", m.__class__.__name__)
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = _clip(content, content_limit)
        else:
            content = _clip(str(content), content_limit)
        item: dict[str, Any] = {"role": role, "content": content}
        tool_calls = _tool_calls_from_message(m)
        if tool_calls:
            item["tool_calls"] = tool_calls
        name = getattr(m, "name", None)
        if name:
            item["name"] = name
        tool_call_id = getattr(m, "tool_call_id", None)
        if tool_call_id:
            item["tool_call_id"] = tool_call_id
        out.append(item)
    return out


def build_trace(
    messages: list[Any],
    *,
    interrupt: Any = None,
    audit: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize messages into UI-friendly steps."""
    serialized = serialize_messages(messages)
    steps: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []

    for msg in serialized:
        role = msg.get("role")
        if role in ("human", "user"):
            steps.append({"kind": "user", "content": msg.get("content", "")})
        elif role in ("ai", "assistant"):
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    step = {
                        "kind": "tool_call",
                        "name": tc.get("name"),
                        "args": tc.get("args"),
                        "id": tc.get("id"),
                    }
                    steps.append(step)
                    tool_calls.append(step)
            content = (msg.get("content") or "").strip()
            if content:
                steps.append({"kind": "assistant", "content": content})
        elif role == "tool":
            steps.append(
                {
                    "kind": "tool_result",
                    "name": msg.get("name"),
                    "content": msg.get("content", ""),
                    "tool_call_id": msg.get("tool_call_id"),
                }
            )
        else:
            steps.append({"kind": role or "other", "content": msg.get("content", "")})

    pending_writes = [
        s
        for s in tool_calls
        if s.get("name")
        in {
            "request_password_reset",
            "request_license_change",
            "close_ticket",
            "escalate_ticket",
        }
    ]

    # Mark Deep Agents `task` tool calls as subagent dispatches
    SUBAGENT_NAMES = {
        "knowledge-research",
        "environment-diagnosis",
        "ticket-operations",
        "general-purpose",
    }
    for step in steps:
        if step.get("kind") != "tool_call" or step.get("name") != "task":
            continue
        args = step.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        sub_name = ""
        if isinstance(args, dict):
            sub_name = str(args.get("subagent_type") or args.get("name") or args.get("agent") or "")
        step["kind"] = "subagent_dispatch"
        step["subagent"] = sub_name or "unknown"
        if sub_name in SUBAGENT_NAMES:
            step["subagent_known"] = True

    subagent_steps = [s for s in steps if s.get("kind") == "subagent_dispatch"]

    return {
        "steps": steps,
        "tool_calls": tool_calls,
        "pending_writes": pending_writes,
        "subagent_dispatches": subagent_steps,
        "interrupt": interrupt,
        "audit": audit or [],
        "messages": serialized,
    }


def extract_interrupt_info(agent: Any, config: dict) -> dict[str, Any] | None:
    from deepsupport_os.harness.hitl_apply import collect_pending_writes, preview_pending_writes

    try:
        state = agent.get_state(config)
    except Exception:  # noqa: BLE001
        return None
    if not state:
        return None
    nxt = list(getattr(state, "next", None) or [])
    if not nxt:
        return None
    values = getattr(state, "values", None) or {}
    interrupts = []
    raw_interrupts = getattr(state, "tasks", None) or ()
    for t in raw_interrupts:
        interrupts.append(str(t))
    # Prefer structured pending writes from latest messages
    msgs = values.get("messages") or []
    trace = build_trace(msgs, interrupt={"next": nxt})
    pending = collect_pending_writes(msgs, pending=trace.get("pending_writes"))
    # Only surface the most recent write tools for HITL UI (avoid historical noise)
    pending = pending[-3:]
    return {
        "next": nxt,
        "pending_writes": pending,
        "pending_preview": preview_pending_writes(pending),
        "tasks": interrupts,
    }
