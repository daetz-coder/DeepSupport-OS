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
    ARTIFACT_HINTS = (
        "diagnosis.md",
        "retrieved_docs.md",
        "final_resolution.md",
        "ticket_draft.md",
        "workspace/",
        "large_tool_results",
    )
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

    # Context offload: write_file/edit_file targeting workspace artifacts
    for step in steps:
        if step.get("kind") != "tool_call" or step.get("name") not in {"write_file", "edit_file"}:
            continue
        args = step.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            continue
        path = str(args.get("file_path") or args.get("path") or args.get("filename") or "")
        if any(h in path.replace("\\", "/") for h in ARTIFACT_HINTS) or path.endswith(".md"):
            step["kind"] = "context_offload"
            step["offload_path"] = path

    subagent_steps = [s for s in steps if s.get("kind") == "subagent_dispatch"]
    offload_steps = [s for s in steps if s.get("kind") == "context_offload"]

    from deepsupport_os.harness.run_overview import enrich_trace

    base = {
        "steps": steps,
        "tool_calls": tool_calls,
        "pending_writes": pending_writes,
        "subagent_dispatches": subagent_steps,
        "context_offloads": offload_steps,
        "interrupt": interrupt,
        "audit": audit or [],
        "messages": serialized,
    }
    return enrich_trace(base)


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    """Messages after the last user utterance (= the current conversation turn)."""
    out: list[Any] = []
    for m in reversed(messages or []):
        role = getattr(m, "type", None)
        if isinstance(m, dict):
            role = m.get("role")
        if role in {"user", "human"}:
            break
        out.insert(0, m)
    return out


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

    interrupts = []
    raw_interrupts = getattr(state, "tasks", None) or ()
    for t in raw_interrupts:
        interrupts.append(str(t))

    # Prefer the actual interrupt value: it tells us exactly which tool calls
    # are waiting (no stale/historical writes leak into the approval preview).
    ask_payload: dict[str, Any] | None = None
    hitl_actions: list[dict[str, Any]] = []
    for ir in getattr(state, "interrupts", None) or ():
        val = getattr(ir, "value", ir)
        if isinstance(val, dict) and val.get("type") == "ask":
            ask_payload = val
            break
        if isinstance(val, str) and val.strip():
            # Bare string interrupt — treat as ask question
            ask_payload = {"type": "ask", "question": val.strip(), "context": ""}
            break
        action_requests = (
            val.get("action_requests")
            if isinstance(val, dict)
            else getattr(val, "action_requests", None)
        )
        if action_requests:
            for ar in action_requests:
                name = ar.get("name") if isinstance(ar, dict) else getattr(ar, "name", None)
                args = ar.get("args") if isinstance(ar, dict) else getattr(ar, "args", {})
                if name:
                    hitl_actions.append({"name": str(name), "args": args or {}})
            break

    if ask_payload:
        return {
            "type": "ask",
            "question": str(ask_payload.get("question") or "请补充信息"),
            "context": str(ask_payload.get("context") or ""),
            "next": nxt,
            "pending_writes": [],
            "pending_preview": [],
            "tasks": interrupts,
        }

    if hitl_actions:
        pending: list[dict[str, Any]] = hitl_actions[-3:]
    else:
        # Fallback (older checkpoints / middleware-style): scan only the current
        # turn so previously-approved writes do not reappear.
        values = getattr(state, "values", None) or {}
        msgs = _current_turn_messages(values.get("messages") or [])
        trace = build_trace(msgs, interrupt={"next": nxt})
        pending = collect_pending_writes(msgs, pending=trace.get("pending_writes"))
        pending = pending[-3:]

    return {
        "type": "hitl",
        "next": nxt,
        "pending_writes": pending,
        "pending_preview": preview_pending_writes(pending),
        "tasks": interrupts,
    }
