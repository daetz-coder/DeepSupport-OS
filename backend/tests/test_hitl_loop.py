"""HITL approval-loop fixes: state-aware write tools + interrupt `when` guards.

After an approval is applied, re-issuing the same write must NOT re-trigger the
approval prompt (tool reports `already_applied`, and `interrupt_on` `when`
auto-approves already-applied actions).
"""

from __future__ import annotations

from deepsupport_os.db.repositories import AccountRepo, TicketRepo
from deepsupport_os.harness.builder import (
    _needs_close,
    _needs_escalate,
    _needs_license_change,
    _needs_password_reset,
)
from deepsupport_os.mcp.tools import (
    close_ticket,
    escalate_ticket,
    request_license_change,
    request_password_reset,
)


class _Req:
    """Minimal ToolCallRequest stand-in for `when` predicates."""

    def __init__(self, args: dict):
        self.tool_call = {"args": args}


def test_password_reset_tool_is_state_aware(fresh_db):
    # locked account -> still needs approval
    first = request_password_reset.invoke({"email": "wei.zhang@contoso.com"})
    assert first["pending_approval"] is True
    assert not first.get("already_applied")

    # apply the reset (as apply_approved_writes does) -> account active
    AccountRepo().apply_password_reset("wei.zhang@contoso.com")
    again = request_password_reset.invoke({"email": "wei.zhang@contoso.com"})
    assert again["already_applied"] is True
    assert "pending_approval" not in again


def test_license_change_tool_is_state_aware(fresh_db):
    target = "Microsoft 365 E5"
    first = request_license_change.invoke(
        {"email": "wei.zhang@contoso.com", "new_license_type": target}
    )
    assert first["pending_approval"] is True

    AccountRepo().apply_license_change("wei.zhang@contoso.com", target)
    again = request_license_change.invoke(
        {"email": "wei.zhang@contoso.com", "new_license_type": target}
    )
    assert again["already_applied"] is True
    assert "pending_approval" not in again


def test_close_and_escalate_tools_are_state_aware(fresh_db):
    t = TicketRepo().create_ticket(title="t", description="d", category="Account")
    tid = t["ticket_id"]

    first_close = close_ticket.invoke({"ticket_id": tid, "resolution": "fixed"})
    assert first_close["pending_approval"] is True

    TicketRepo().update_ticket(tid, allow_terminal=True, status="closed", resolution="fixed")
    again_close = close_ticket.invoke({"ticket_id": tid, "resolution": "fixed"})
    assert again_close["already_applied"] is True
    assert "pending_approval" not in again_close

    first_esc = escalate_ticket.invoke({"ticket_id": tid, "reason": "needs L2"})
    assert first_esc["pending_approval"] is True
    TicketRepo().update_ticket(
        tid, allow_terminal=True, status="escalated", priority="P1", assignee="L2 Support"
    )
    again_esc = escalate_ticket.invoke({"ticket_id": tid, "reason": "needs L2"})
    assert again_esc["already_applied"] is True
    assert "pending_approval" not in again_esc


def test_interrupt_when_predicates_guard_reapproval(fresh_db):
    email = "wei.zhang@contoso.com"
    # locked -> interrupt; active -> auto-approve
    assert _needs_password_reset(_Req({"email": email})) is True
    AccountRepo().apply_password_reset(email)
    assert _needs_password_reset(_Req({"email": email})) is False

    # license: current E3, target E5 -> interrupt; after apply -> auto-approve
    assert (
        _needs_license_change(_Req({"email": email, "new_license_type": "Microsoft 365 E5"}))
        is True
    )
    AccountRepo().apply_license_change(email, "Microsoft 365 E5")
    assert (
        _needs_license_change(_Req({"email": email, "new_license_type": "Microsoft 365 E5"}))
        is False
    )

    # ticket: open -> interrupt; closed/escalated -> auto-approve
    t = TicketRepo().create_ticket(title="t", description="d", category="Account")
    tid = t["ticket_id"]
    assert _needs_close(_Req({"ticket_id": tid})) is True
    assert _needs_escalate(_Req({"ticket_id": tid})) is True
    TicketRepo().update_ticket(tid, allow_terminal=True, status="closed", resolution="done")
    assert _needs_close(_Req({"ticket_id": tid})) is False
    TicketRepo().update_ticket(
        tid, allow_terminal=True, status="escalated", priority="P1", assignee="L2 Support"
    )
    assert _needs_escalate(_Req({"ticket_id": tid})) is False
