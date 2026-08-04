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
    "close_ticket",
    "escalate_ticket",
}


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def collect_pending_writes(messages: list[Any] | None = None, pending: list[dict] | None = None) -> list[dict[str, Any]]:
    """Collect latest pending write tool calls (dedupe by tool+args)."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(name: str, args: dict[str, Any]) -> None:
        key = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        if key in seen:
            return
        seen.add(key)
        found.append({"name": name, "args": args})

    for item in pending or []:
        name = item.get("name")
        if name in WRITE_TOOLS:
            _add(name, _parse_args(item.get("args")))

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
                    _add(name, args)
            continue
        # Also recover from tool result payloads that marked pending_approval
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) in WRITE_TOOLS:
            try:
                payload = json.loads(str(m.content))
            except Exception:  # noqa: BLE001
                payload = {}
            if isinstance(payload, dict) and payload.get("pending_approval"):
                args = {k: v for k, v in payload.items() if k not in {"ok", "pending_approval", "action"}}
                # map common fields
                if "email" in payload:
                    args["email"] = payload["email"]
                if "ticket_id" in payload:
                    args["ticket_id"] = payload["ticket_id"]
                if "resolution" in payload:
                    args["resolution"] = payload["resolution"]
                if "new_license_type" in payload:
                    args["new_license_type"] = payload["new_license_type"]
                _add(str(m.name), args)

    return found


def apply_approved_writes(
    writes: list[dict[str, Any]],
    *,
    task_id: str = "hitl",
) -> list[dict[str, Any]]:
    """Execute side effects for approved write tools."""
    results: list[dict[str, Any]] = []
    for w in writes:
        name = w.get("name")
        args = _parse_args(w.get("args"))
        result: dict[str, Any]
        if name == "request_password_reset":
            email = args.get("email") or ""
            result = _account.apply_password_reset(email)
        elif name == "request_license_change":
            email = args.get("email") or ""
            new_type = args.get("new_license_type") or args.get("license_type") or ""
            result = _account.apply_license_change(email, new_type)
        elif name == "close_ticket":
            ticket_id = args.get("ticket_id") or ""
            resolution = args.get("resolution") or "Closed after approval"
            updated = _ticket.update_ticket(
                ticket_id,
                allow_terminal=True,
                status="closed",
                resolution=resolution,
            )
            result = {"ok": bool(updated) and updated.get("status") == "closed", "ticket": updated, "action": "close_ticket"}
        elif name == "escalate_ticket":
            ticket_id = args.get("ticket_id") or ""
            reason = args.get("reason") or "Escalated after approval"
            updated = _ticket.update_ticket(
                ticket_id,
                allow_terminal=True,
                status="escalated",
                priority="P1",
                assignee="L2 Support",
                resolution=f"Escalation reason: {reason}",
            )
            result = {"ok": bool(updated) and updated.get("status") == "escalated", "ticket": updated, "action": "escalate_ticket"}
        else:
            result = {"ok": False, "error": f"unsupported_write:{name}"}
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
