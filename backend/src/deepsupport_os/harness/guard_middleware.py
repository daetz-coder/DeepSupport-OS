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

# Evidence that the agent (or env subagent) actually inspected account/ticket state.
_ACCOUNT_DIAGNOSIS = frozenset({"get_account_status", "get_employee", "get_license"})
_TICKET_DIAGNOSIS = frozenset({"get_ticket"})


def _had_subagent_task(messages: list[Any], subagent_type: str) -> bool:
    """True if a completed `task` tool call targeted this subagent_type."""
    wanted = subagent_type.strip().lower()
    pending_ids: set[str] = set()
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            if isinstance(tc, dict):
                name = str(tc.get("name") or "")
                args = tc.get("args") or {}
                tc_id = str(tc.get("id") or "")
            else:
                name = str(getattr(tc, "name", "") or "")
                args = getattr(tc, "args", None) or {}
                tc_id = str(getattr(tc, "id", "") or "")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            if name == "task" and str(args.get("subagent_type") or "").strip().lower() == wanted:
                if tc_id:
                    pending_ids.add(tc_id)
                else:
                    return True
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) == "task":
            tid = str(getattr(m, "tool_call_id", "") or "")
            if tid and tid in pending_ids:
                return True
            # Fallback: content often embeds subagent output; accept any completed task
            # if we already saw a matching dispatch without id.
            if not pending_ids and wanted in str(getattr(m, "content", "") or "").lower():
                return True
    return False


def _has_diagnosis_for_write(name: str, messages: list[Any]) -> bool:
    seen = _recent_tool_names(messages)
    if name == "request_password_reset":
        return bool(seen & _ACCOUNT_DIAGNOSIS) or _had_subagent_task(
            messages, "environment-diagnosis"
        )
    if name == "request_license_change":
        return bool(seen & _ACCOUNT_DIAGNOSIS) or _had_subagent_task(
            messages, "environment-diagnosis"
        )
    if name in {"close_ticket", "escalate_ticket"}:
        return bool(seen & _TICKET_DIAGNOSIS) or _had_subagent_task(
            messages, "ticket-operations"
        )
    return True


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


def _prior_ask_questions(
    messages: list[Any], *, exclude_ids: set[str] | None = None
) -> list[str]:
    """Questions from prior ask_user tool_calls (not the in-flight call / error denials)."""
    skip = set(exclude_ids or ())
    skip |= _error_tool_call_ids(messages)
    out: list[str] = []
    for m in messages:
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) == "ask_user":
            # Content is the answer; look at prior AI tool_calls for question — skip.
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if not isinstance(tc, dict) or tc.get("name") != "ask_user":
                continue
            tid = str(tc.get("id") or "")
            if tid and tid in skip:
                continue
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


def _tool_signature(name: str, args: dict[str, Any]) -> str:
    """Stable key for duplicate detection (tool + canonical args)."""
    if name == "get_document":
        key = str(args.get("document_id") or "").strip().lower()
    elif name in {"search_docs", "search_cases"}:
        key = str(args.get("query") or "").strip().lower()
    elif name in {"get_employee", "get_account_status", "get_license", "list_user_devices"}:
        key = str(args.get("email") or args.get("employee_id") or "").strip().lower()
    elif name in {"get_device"}:
        key = str(args.get("device_id") or "").strip().lower()
    elif name in {"get_ticket", "update_ticket", "create_ticket"}:
        key = str(args.get("ticket_id") or args.get("idempotency_key") or "").strip().lower()
    else:
        try:
            key = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
        except TypeError:
            key = str(args)
    return f"{name}::{key}"


def _is_human_message(m: Any) -> bool:
    t = getattr(m, "type", None) or getattr(m, "role", None)
    return str(t or "").lower() in {"human", "user"}


def _messages_since_last_human(messages: list[Any]) -> list[Any]:
    """Current-turn window so prior-turn tools are not permanently blocked."""
    for i in range(len(messages) - 1, -1, -1):
        if _is_human_message(messages[i]):
            return messages[i + 1 :]
    return messages


def _error_tool_call_ids(messages: list[Any]) -> set[str]:
    """Tool call ids that already returned an error ToolMessage (safe to retry)."""
    out: set[str] = set()
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        if getattr(m, "status", None) != "error":
            continue
        tid = str(getattr(m, "tool_call_id", "") or "")
        if tid:
            out.add(tid)
    return out


def _prior_tool_signatures(
    messages: list[Any],
    *,
    limit: int = 80,
    exclude_ids: set[str] | None = None,
) -> list[str]:
    """Signatures from prior AI tool_calls (args available there).

    Excludes ``exclude_ids`` (must include the *current* tool_call id — the
    AIMessage is already in state when wrap_tool_call runs, so without this
    every call looks like a duplicate of itself).
    Also skips ids that only produced ``status=error`` ToolMessages so a
    denied/failed call can be retried after fixing the cause.
    """
    skip = set(exclude_ids or ())
    skip |= _error_tool_call_ids(messages)
    out: list[str] = []
    for m in messages[-limit:]:
        for tc in getattr(m, "tool_calls", None) or []:
            if isinstance(tc, dict):
                name = str(tc.get("name") or "")
                args = tc.get("args") or {}
                tc_id = str(tc.get("id") or "")
            else:
                name = str(getattr(tc, "name", "") or "")
                args = getattr(tc, "args", None) or {}
                tc_id = str(getattr(tc, "id", "") or "")
            if tc_id and tc_id in skip:
                continue
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            if not isinstance(args, dict):
                args = {}
            if name:
                out.append(_tool_signature(name, args))
    return out


def apply_support_tool_guards(
    request: Any,
    handler: Callable[[Any], Any],
    *,
    max_calls: int | None = None,
) -> Any:
    """Block common Prompt-only rules with hard middleware checks."""
    name = _tool_name(request)
    messages = _state_messages(request)
    todos = _state_todos(request)
    turn_messages = _messages_since_last_human(messages)

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
    # Exclude the in-flight tool_call id — it is already on the AIMessage in state.
    if name == "ask_user":
        question = str(_tool_args(request).get("question") or "").strip().lower()
        current_id = _tool_call_id(request)
        prior_qs = _prior_ask_questions(
            messages, exclude_ids={current_id} if current_id else set()
        )
        if question and question in prior_qs:
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "ask_user_duplicate",
                    "hint": "该问题已提问过；请使用用户已提供的回答继续，勿重复 ask_user",
                },
            )

    # 2b) Never create_ticket in the same turn as escalate/close of a real ticket.
    if name == "create_ticket":
        from deepsupport_os.db.repositories import TicketRepo

        ticket_repo = TicketRepo()
        for m in reversed(turn_messages[-8:]):
            for tc in getattr(m, "tool_calls", None) or []:
                if isinstance(tc, dict):
                    tc_name = tc.get("name")
                    tc_args = tc.get("args") or {}
                else:
                    tc_name = getattr(tc, "name", None)
                    tc_args = getattr(tc, "args", None) or {}
                if tc_name not in {"escalate_ticket", "close_ticket"}:
                    continue
                if isinstance(tc_args, str):
                    try:
                        tc_args = json.loads(tc_args)
                    except json.JSONDecodeError:
                        tc_args = {}
                tid = str((tc_args or {}).get("ticket_id") or "")
                if tid and ticket_repo.get_ticket(tid):
                    return ToolMessage(
                        content=json.dumps(
                            {
                                "ok": True,
                                "already_applied": True,
                                "skipped": "create_while_escalate_or_close",
                                "hint": (
                                    f"工单 {tid} 已存在；本轮请 escalate/close，"
                                    "勿再 create_ticket"
                                ),
                                "ticket_id": tid,
                            },
                            ensure_ascii=False,
                        ),
                        tool_call_id=_tool_call_id(request),
                        name=_tool_name(request) or "create_ticket",
                    )

    # 2c) Same-signature tool replay + per-turn tool budget (main agent).
    # Scope to the current user turn; exclude self id / prior error ids.
    if name:
        args = _tool_args(request)
        sig = _tool_signature(name, args)
        current_id = _tool_call_id(request)
        prior_sigs = _prior_tool_signatures(
            turn_messages, exclude_ids={current_id} if current_id else set()
        )
        if sig in prior_sigs:
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "duplicate_tool_call",
                    "hint": (
                        f"工具 {name} 已用相同参数调用过；请复用已有结果继续，"
                        "禁止无效重复调用"
                    ),
                    "blocked_tool": name,
                    "signature": sig,
                },
            )
        limit = max_calls if max_calls is not None else _main_max_tool_calls()
        if len(prior_sigs) >= limit:
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "main_tool_budget_exhausted",
                    "hint": (
                        f"主代理工具预算已用尽（最多 {limit} 次）；"
                        "请基于已有结果给出结论或 ask_user，勿继续盲目调工具"
                    ),
                    "blocked_tool": name,
                    "max_calls": limit,
                    "used_calls": len(prior_sigs),
                },
            )

    # 3) High-risk writes require prior diagnosis evidence (block premature HITL).
    if name in _WRITE_INTENT and not _has_diagnosis_for_write(name, messages):
        return _deny(
            request,
            {
                "ok": False,
                "error": "diagnosis_required",
                "hint": (
                    "高风险写操作前必须先完成环境/工单诊断："
                    "先 get_account_status（或委派 environment-diagnosis），"
                    "再 check_action_permission，最后才可申请写操作"
                ),
                "blocked_tool": name,
            },
        )

    # 4) High-risk writes need a *passing* policy check for THIS action (not just
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


# Default budget for MVP subagents (business tools only; FS/skill reads exempt).
# Env diagnosis often needs employee + account + license + devices (≥4).
_SUBAGENT_MAX_TOOL_CALLS = 6
# Fallback when settings unavailable (tests / import edge cases).
_MAIN_MAX_TOOL_CALLS = 24

# Progressive-disclosure skill / filesystem tools must not burn the business budget.
_SUBAGENT_BUDGET_EXEMPT = frozenset(
    {
        "read_file",
        "write_file",
        "edit_file",
        "ls",
        "glob",
        "grep",
        "execute",
    }
)


def _main_max_tool_calls() -> int:
    try:
        from deepsupport_os.core.config import get_settings

        return int(get_settings().agent_max_tool_calls)
    except Exception:  # noqa: BLE001
        return _MAIN_MAX_TOOL_CALLS


def _budget_used(prior_sigs: list[str]) -> int:
    """Count only non-exempt tool signatures toward the subagent call budget."""
    n = 0
    for sig in prior_sigs:
        name = sig.split("::", 1)[0]
        if name not in _SUBAGENT_BUDGET_EXEMPT:
            n += 1
    return n


def apply_subagent_tool_budget(
    request: Any,
    handler: Callable[[Any], Any],
    *,
    max_calls: int = _SUBAGENT_MAX_TOOL_CALLS,
) -> Any:
    """Hard-stop repeated / excess tool use inside subagents (prompt alone is ignored)."""
    name = _tool_name(request)
    if not name:
        return handler(request)

    messages = _state_messages(request)
    args = _tool_args(request)
    sig = _tool_signature(name, args)
    current_id = _tool_call_id(request)
    prior_sigs = _prior_tool_signatures(
        messages, exclude_ids={current_id} if current_id else set()
    )

    if sig in prior_sigs:
        return _deny(
            request,
            {
                "ok": False,
                "error": "duplicate_tool_call",
                "hint": (
                    f"工具 {name} 已用相同参数调用过；请复用已有结果并立即输出最终结构化答案，"
                    "禁止重复检索/重复拉取同一文档"
                ),
                "blocked_tool": name,
                "signature": sig,
            },
        )

    # FS/skill reads are exempt; only business tools count toward max_calls.
    if name not in _SUBAGENT_BUDGET_EXEMPT:
        used = _budget_used(prior_sigs)
        if used >= max_calls:
            return _deny(
                request,
                {
                    "ok": False,
                    "error": "subagent_tool_budget_exhausted",
                    "hint": (
                        f"子代理业务工具预算已用尽（最多 {max_calls} 次）；"
                        "请立即基于已有检索结果输出最终结构化答案，勿再调用工具"
                    ),
                    "blocked_tool": name,
                    "max_calls": max_calls,
                    "used_calls": used,
                },
            )

    return handler(request)


@wrap_tool_call
def subagent_tool_budget(
    request: Any,
    handler: Callable[[Any], Any],
) -> Any:
    return apply_subagent_tool_budget(request, handler)


def support_guard_middleware() -> list[Any]:
    """Return middleware list entry for HarnessBuilder."""
    return [support_tool_guards]


def subagent_budget_middleware() -> list[Any]:
    """Middleware for MVP subagents: cap + dedupe tool calls."""
    return [subagent_tool_budget]
