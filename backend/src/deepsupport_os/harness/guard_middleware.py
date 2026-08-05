"""Hardening middleware: enforce todos / ask dedupe before tools (R3-1 / AR-10)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage

from deepsupport_os.mcp.tools import POLICY_ACTION_FOR_TOOL

# Tools allowed before a todos plan exists.
_PRE_TODO_ALLOW = frozenset(
    {
        "write_todos",
        "read_todos",
        "ask_user",
        "task",  # subagent dispatch may still need a plan; keep narrow
    }
)

_WRITE_INTENT = frozenset(
    {
        "request_password_reset",
        "request_license_change",
        "close_ticket",
        "escalate_ticket",
    }
)

# How far back to look for a passing check_action_permission result.
_SCAN_WINDOW = 40


def _tool_name(request: Any) -> str:
    tc = getattr(request, "tool_call", None) or {}
    if isinstance(tc, dict):
        return str(tc.get("name") or "")
    return str(getattr(tc, "name", "") or "")


def _tool_call_id(request: Any) -> str:
    tc = getattr(request, "tool_call", None) or {}
    if isinstance(tc, dict):
        return str(tc.get("id") or "guard")
    return str(getattr(tc, "id", None) or "guard")


def _tool_args(request: Any) -> dict[str, Any]:
    tc = getattr(request, "tool_call", None) or {}
    if isinstance(tc, dict):
        args = tc.get("args") or {}
    else:
        args = getattr(tc, "args", None) or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return args if isinstance(args, dict) else {}


def _state_messages(request: Any) -> list[Any]:
    state = getattr(request, "state", None) or {}
    if isinstance(state, dict):
        return list(state.get("messages") or [])
    return list(getattr(state, "messages", None) or [])


def _state_todos(request: Any) -> list[Any]:
    state = getattr(request, "state", None) or {}
    if isinstance(state, dict):
        return list(state.get("todos") or [])
    return list(getattr(state, "todos", None) or [])


def _recent_tool_names(messages: list[Any], *, limit: int = 40) -> set[str]:
    names: set[str] = set()
    for m in messages[-limit:]:
        name = getattr(m, "name", None)
        if getattr(m, "type", None) == "tool" and name:
            names.add(str(name))
        for tc in getattr(m, "tool_calls", None) or []:
            if isinstance(tc, dict) and tc.get("name"):
                names.add(str(tc["name"]))
            else:
                n = getattr(tc, "name", None)
                if n:
                    names.add(str(n))
    return names


def _prior_ask_questions(messages: list[Any]) -> list[str]:
    out: list[str] = []
    for m in messages:
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) == "ask_user":
            # Content is the answer; look at prior AI tool_calls for question — skip.
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if isinstance(tc, dict) and tc.get("name") == "ask_user":
                args = tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                q = str((args or {}).get("question") or "").strip().lower()
                if q:
                    out.append(q)
    return out


def _policy_permits(messages: list[Any], expected_action: str) -> bool:
    """Most recent ``check_action_permission`` result must hit this policy action.

    The result is the tool's return value: a found entry carries ``action`` +
    ``approval_required``; a miss carries ``{"error": "policy_not_found"}``.
    Requiring the canonical action match prevents checking an unrelated action
    (e.g. ``read_employee``) to satisfy a write tool's gate (AR-15 / R3-1).
    """
    for m in reversed(messages[-_SCAN_WINDOW:]):
        if getattr(m, "type", None) != "tool":
            continue
        if getattr(m, "name", None) != "check_action_permission":
            continue
        raw = getattr(m, "content", None)
        payload = raw if isinstance(raw, dict) else None
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None
        if not isinstance(payload, dict):
            return False
        # policy_not_found / error payloads carry no entry → no gate.
        if "approval_required" not in payload:
            return False
        if str(payload.get("action") or "") != expected_action:
            return False
        return True
    return False


def _deny(request: Any, payload: dict[str, Any]) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(payload, ensure_ascii=False),
        tool_call_id=_tool_call_id(request),
        name=_tool_name(request) or "guard",
        status="error",
    )


def apply_support_tool_guards(
    request: Any,
    handler: Callable[[Any], Any],
) -> Any:
    """Block common Prompt-only rules with hard middleware checks."""
    name = _tool_name(request)
    messages = _state_messages(request)
    todos = _state_todos(request)

    # 1) Must plan before other tools (skip on resume turns that already have todos).
    if name and name not in _PRE_TODO_ALLOW and not todos:
        # Allow if write_todos already ran earlier in the transcript.
        if "write_todos" not in _recent_tool_names(messages):
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "todos_required",
                    "hint": "先调用 write_todos 建立/刷新排障计划，再调用其它工具",
                    "blocked_tool": name,
                },
            )

    # 2) Duplicate ask_user for the same question.
    if name == "ask_user":
        question = str(_tool_args(request).get("question") or "").strip().lower()
        if question and question in _prior_ask_questions(messages):
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "ask_user_duplicate",
                    "hint": "该问题已提问过；请使用用户已提供的回答继续，勿重复 ask_user",
                    "question": question,
                },
            )

    # 3) High-risk writes need a *passing* policy check for THIS action (not just
    #    a call to check_action_permission for any action) — AR-15 / R3-1.
    if name in _WRITE_INTENT:
        expected = POLICY_ACTION_FOR_TOOL.get(name)
        if not expected or not _policy_permits(messages, expected):
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "policy_check_required",
                    "hint": (
                        "高风险写操作前必须 check_action_permission 且返回该 action 的策略条目"
                        f"（action={expected!r}，approval_required 存在）；"
                        "查其它 action 或策略未命中不算数"
                    ),
                    "blocked_tool": name,
                    "required_policy_action": expected,
                },
            )

    return handler(request)


@wrap_tool_call
def support_tool_guards(
    request: Any,
    handler: Callable[[Any], Any],
) -> Any:
    return apply_support_tool_guards(request, handler)


def support_guard_middleware() -> list[Any]:
    """Return middleware list entry for HarnessBuilder."""
    return [support_tool_guards]
