"""Apply approved high-risk write operations after HITL resume."""

from __future__ import annotations

import json
import re
from typing import Any

from deepsupport_os.db.repositories import AccountRepo, TicketRepo, write_audit

_account = AccountRepo()
_ticket = TicketRepo()

WRITE_TOOLS = {
    "request_password_reset",
    "request_license_change",
    "create_ticket",
    "close_ticket",
    "escalate_ticket",
}

WRITE_LABELS = {
    "request_password_reset": "密码重置",
    "request_license_change": "许可证变更",
    "create_ticket": "创建工单",
    "close_ticket": "关闭工单",
    "escalate_ticket": "升级工单",
}

_HIGHLIGHT_KEYS = (
    ("email", "邮箱"),
    ("ticket_id", "工单 ID"),
    ("title", "标题"),
    ("new_license_type", "新许可证"),
    ("license_type", "许可证"),
    ("resolution", "处理说明"),
    ("reason", "升级原因"),
)


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def canonicalize_write_args(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize write args so empty idempotency_key / whitespace do not fork HITL cards."""
    cleaned: dict[str, Any] = {}
    for k, v in (_parse_args(args) or {}).items():
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                continue
        cleaned[k] = v
    for noise in ("ok", "pending_approval", "action", "message", "already_applied", "hint"):
        cleaned.pop(noise, None)

    if name == "create_ticket":
        out = {
            "title": str(cleaned.get("title") or ""),
            "description": str(cleaned.get("description") or ""),
            "category": str(cleaned.get("category") or "General"),
            "priority": str(cleaned.get("priority") or "P3"),
            "employee_id": str(cleaned.get("employee_id") or ""),
        }
        if cleaned.get("idempotency_key"):
            out["idempotency_key"] = str(cleaned["idempotency_key"])
        return out
    if name == "request_license_change":
        out = {"email": str(cleaned.get("email") or "")}
        lic = cleaned.get("new_license_type") or cleaned.get("license_type")
        if lic:
            out["new_license_type"] = str(lic)
        return out
    if name == "request_password_reset":
        return {"email": str(cleaned.get("email") or "")}
    if name in {"close_ticket", "escalate_ticket"}:
        out = {"ticket_id": str(cleaned.get("ticket_id") or "")}
        if cleaned.get("resolution"):
            out["resolution"] = str(cleaned["resolution"])
        if cleaned.get("reason"):
            out["reason"] = str(cleaned["reason"])
        return out
    return cleaned


def write_dedupe_key(name: str, args: dict[str, Any] | None) -> str:
    """Stable identity for pending HITL cards (collapse near-duplicate tool calls)."""
    c = canonicalize_write_args(name, args)
    if name == "create_ticket":
        return "create_ticket::{title}::{emp}".format(
            title=str(c.get("title") or "").strip().lower(),
            emp=str(c.get("employee_id") or "").strip().lower(),
        )
    if name == "request_license_change":
        return "request_license_change::{email}::{lic}".format(
            email=str(c.get("email") or "").strip().lower(),
            lic=str(c.get("new_license_type") or "").strip().lower(),
        )
    if name == "request_password_reset":
        return f"request_password_reset::{str(c.get('email') or '').strip().lower()}"
    if name in {"close_ticket", "escalate_ticket"}:
        return f"{name}::{str(c.get('ticket_id') or '').strip().lower()}"
    return f"{name}:{json.dumps(c, sort_keys=True, ensure_ascii=False, default=str)}"


def write_idempotency_key(name: str, args: dict[str, Any] | None) -> str:
    """Exactly-once ledger key — same identity as HITL cards (ignore description/reason drift)."""
    from deepsupport_os.db.repositories import make_idempotency_key

    return make_idempotency_key(name, {"_dedupe": write_dedupe_key(name, args)})


def write_needs_hitl(name: str, args: dict[str, Any] | None) -> bool:
    """True when this write should interrupt for human approval."""
    from deepsupport_os.db.repositories import lookup_applied_action, make_idempotency_key

    canon = canonicalize_write_args(name, args)
    if lookup_applied_action(write_idempotency_key(name, canon)):
        return False
    # Legacy ledger rows hashed full args (description/reason included).
    if lookup_applied_action(make_idempotency_key(name, canon)):
        return False

    if name == "create_ticket":
        if _ticket.get_by_idempotency_key(write_dedupe_key(name, canon)):
            return False
        emp = str(canon.get("employee_id") or "")
        title = str(canon.get("title") or "")
        if emp and title and _ticket.find_by_employee_and_title(emp, title):
            return False
        return True
    if name == "escalate_ticket":
        ticket_id = str(canon.get("ticket_id") or "")
        ticket = _ticket.get_ticket(ticket_id) if ticket_id else None
        return not ticket or ticket.get("status") != "escalated"
    if name == "close_ticket":
        ticket_id = str(canon.get("ticket_id") or "")
        ticket = _ticket.get_ticket(ticket_id) if ticket_id else None
        return not ticket or ticket.get("status") != "closed"
    if name == "request_password_reset":
        email = str(canon.get("email") or "")
        account = _account.get_account_status(email) if email else None
        return not account or account.get("status") != "active"
    if name == "request_license_change":
        email = str(canon.get("email") or "")
        target = str(canon.get("new_license_type") or "")
        account = _account.get_account_status(email) if email else None
        return not account or account.get("license_type") != target
    return True


def _cohere_pending_writes(writes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop create_ticket when escalate/close already targets a real ticket."""
    real_ticket = False
    for w in writes:
        if w.get("name") not in {"escalate_ticket", "close_ticket"}:
            continue
        tid = str(canonicalize_write_args(str(w["name"]), w.get("args")).get("ticket_id") or "")
        if tid and _ticket.get_ticket(tid):
            real_ticket = True
            break
    if not real_ticket:
        return writes
    return [w for w in writes if w.get("name") != "create_ticket"]


def preview_pending_write(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """UI-friendly summary of one pending HITL write."""
    args = canonicalize_write_args(name, args or {})
    highlights = [
        {"key": label, "value": str(args[field])}
        for field, label in _HIGHLIGHT_KEYS
        if args.get(field) not in (None, "")
    ]
    return {
        "name": name,
        "label": WRITE_LABELS.get(name, name),
        "highlights": highlights,
        "args": args,
    }


def preview_pending_writes(writes: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in writes or []:
        name = w.get("name")
        if not name:
            continue
        out.append(preview_pending_write(str(name), _parse_args(w.get("args"))))
    return out


def collect_pending_writes(messages: list[Any] | None = None, pending: list[dict] | None = None) -> list[dict[str, Any]]:
    """Collect latest pending write tool calls (dedupe by semantic write identity)."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(name: str, args: dict[str, Any]) -> None:
        canon = canonicalize_write_args(name, args)
        key = write_dedupe_key(name, canon)
        if key in seen:
            return
        seen.add(key)
        found.append({"name": name, "args": canon})

    for item in pending or []:
        name = item.get("name")
        if name in WRITE_TOOLS:
            _add(str(name), _parse_args(item.get("args")))

    for m in messages or []:
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name")
                    args = _parse_args(tc.get("args"))
                else:
                    name = getattr(tc, "name", None)
                    args = _parse_args(getattr(tc, "args", {}))
                if name in WRITE_TOOLS:
                    _add(str(name), args)
            continue
        # Also recover from tool result payloads that marked pending_approval
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) in WRITE_TOOLS:
            try:
                payload = json.loads(str(m.content))
            except Exception:  # noqa: BLE001
                payload = {}
            if isinstance(payload, dict) and payload.get("pending_approval"):
                args = {
                    k: v
                    for k, v in payload.items()
                    if k not in {"ok", "pending_approval", "action", "message", "already_applied"}
                }
                _add(str(m.name), args)

    # Drop already-applied / no-op writes, then create vs escalate/close coherence.
    needed = [w for w in found if write_needs_hitl(str(w["name"]), w.get("args"))]
    return _cohere_pending_writes(needed)


def apply_approved_writes(
    writes: list[dict[str, Any]],
    *,
    task_id: str = "hitl",
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    """Execute side effects for approved write tools (Single Executor + Exactly Once)."""
    from deepsupport_os.db.repositories import (
        lookup_applied_action,
        make_idempotency_key,
        record_applied_action,
    )

    results: list[dict[str, Any]] = []
    for w in writes:
        name = str(w.get("name") or "")
        args = canonicalize_write_args(name, _parse_args(w.get("args")))
        key = write_idempotency_key(name, args)
        prior = lookup_applied_action(key)
        if not prior:
            # Legacy full-args ledger entries from before semantic keys.
            prior = lookup_applied_action(make_idempotency_key(name, args))
        if prior and isinstance(prior.get("result"), dict):
            result = dict(prior["result"])
            result.setdefault("ok", True)
            result.setdefault("already_applied", True)
            result.setdefault("idempotency_key", key)
            write_audit(task_id, f"hitl_apply:{name}", args, result)
            results.append({"tool": name, "args": args, "result": result})
            continue

        result: dict[str, Any]
        if name == "request_password_reset":
            email = args.get("email") or ""
            result = _account.apply_password_reset(email)
        elif name == "request_license_change":
            email = args.get("email") or ""
            new_type = args.get("new_license_type") or args.get("license_type") or ""
            result = _account.apply_license_change(email, new_type)
        elif name == "create_ticket":
            ticket_key = args.get("idempotency_key") or write_dedupe_key(name, args)
            created = _ticket.create_ticket(
                title=str(args.get("title") or "Support ticket"),
                description=str(args.get("description") or ""),
                category=str(args.get("category") or "General"),
                priority=str(args.get("priority") or "P3"),
                employee_id=args.get("employee_id") or None,
                idempotency_key=ticket_key,
            )
            if isinstance(created, dict) and created.get("ticket_id"):
                result = {
                    "ok": True,
                    "ticket": created,
                    "action": "create_ticket",
                    "ticket_id": created.get("ticket_id"),
                }
            else:
                result = {
                    "ok": False,
                    "error": "create_ticket_failed",
                    "detail": created,
                }
        elif name == "close_ticket":
            ticket_id = args.get("ticket_id") or ""
            resolution = args.get("resolution") or "Closed after approval"
            current = _ticket.get_ticket(ticket_id)
            if current and current.get("status") == "closed":
                result = {
                    "ok": True,
                    "already_applied": True,
                    "ticket": current,
                    "action": "close_ticket",
                }
            else:
                updated = _ticket.update_ticket(
                    ticket_id,
                    allow_terminal=True,
                    status="closed",
                    resolution=resolution,
                )
                result = {
                    "ok": bool(updated) and updated.get("status") == "closed",
                    "ticket": updated,
                    "action": "close_ticket",
                }
        elif name == "escalate_ticket":
            ticket_id = args.get("ticket_id") or ""
            reason = args.get("reason") or "Escalated after approval"
            current = _ticket.get_ticket(ticket_id)
            if current and current.get("status") == "escalated":
                result = {
                    "ok": True,
                    "already_applied": True,
                    "ticket": current,
                    "action": "escalate_ticket",
                }
            else:
                updated = _ticket.update_ticket(
                    ticket_id,
                    allow_terminal=True,
                    status="escalated",
                    priority="P1",
                    assignee="L2 Support",
                    resolution=f"Escalation reason: {reason}",
                )
                result = {
                    "ok": bool(updated) and updated.get("status") == "escalated",
                    "ticket": updated,
                    "action": "escalate_ticket",
                }
        else:
            result = {"ok": False, "error": f"unsupported_write:{name}"}

        if result.get("ok"):
            result = record_applied_action(
                tool=str(name),
                args=args,
                result=result,
                task_id=task_id,
                thread_id=thread_id,
                idempotency_key=key,
            )
            result.setdefault("idempotency_key", key)

        write_audit(task_id, f"hitl_apply:{name}", args, result)
        results.append({"tool": name, "args": args, "result": result})
    return results


def infer_email_from_messages(messages: list[Any]) -> str | None:
    pattern = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
    for m in reversed(messages or []):
        content = str(getattr(m, "content", "") or "")
        match = pattern.search(content)
        if match:
            return match.group(0)
    return None
