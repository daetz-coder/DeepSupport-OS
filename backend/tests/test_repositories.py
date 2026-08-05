from deepsupport_os.db.repositories import AccountRepo, EmployeeRepo, TicketRepo
from deepsupport_os.harness.hitl_apply import apply_approved_writes, collect_pending_writes


def test_employee_by_email(fresh_db):
    emp = EmployeeRepo().get_by_email("wei.zhang@contoso.com")
    assert emp is not None
    assert emp["employee_id"] == "E001"


def test_account_locked_demo(fresh_db):
    acct = AccountRepo().get_account_status("wei.zhang@contoso.com")
    assert acct["status"] == "locked"


def test_hitl_password_reset_apply(fresh_db):
    class Msg:
        type = "ai"
        content = ""
        tool_calls = [
            {
                "id": "1",
                "name": "request_password_reset",
                "args": {"email": "wei.zhang@contoso.com"},
            }
        ]

    pending = collect_pending_writes([Msg()])
    assert pending[0]["name"] == "request_password_reset"
    results = apply_approved_writes(pending, task_id="test")
    assert results[0]["result"]["ok"] is True
    assert AccountRepo().get_account_status("wei.zhang@contoso.com")["status"] == "active"


def test_hitl_resume_apply_license_and_close(fresh_db):
    """Smoke: approved writes apply without needing a live LLM resume."""
    from deepsupport_os.db.repositories import AccountRepo, TicketRepo
    from deepsupport_os.harness.hitl_apply import apply_approved_writes

    pending = [
        {
            "name": "request_license_change",
            "args": {
                "email": "wei.zhang@contoso.com",
                "new_license_type": "Microsoft 365 E5",
            },
        }
    ]
    # license change is intent-only in tools; apply path must still be safe
    results = apply_approved_writes(pending, task_id="hitl-lic")
    assert results[0]["result"]["ok"] is True
    assert (
        AccountRepo().get_account_status("wei.zhang@contoso.com")["license_type"]
        == "Microsoft 365 E5"
    )

    t = TicketRepo().create_ticket(title="x", description="y", category="Account")
    closed = apply_approved_writes(
        [
            {
                "name": "close_ticket",
                "args": {"ticket_id": t["ticket_id"], "resolution": "fixed"},
            }
        ],
        task_id="hitl-close",
    )
    assert closed[0]["result"]["ok"] is True
    assert TicketRepo().get_ticket(t["ticket_id"])["status"] == "closed"


def test_update_ticket_blocks_terminal_without_hitl(fresh_db):
    t = TicketRepo().create_ticket(title="t", description="d", category="Account")
    blocked = TicketRepo().update_ticket(t["ticket_id"], status="closed")
    assert blocked["error"] == "terminal_status_requires_hitl"
    closed = TicketRepo().update_ticket(
        t["ticket_id"], allow_terminal=True, status="closed", resolution="done"
    )
    assert closed["status"] == "closed"


def test_update_ticket_tool_supports_priority_and_rejects_bad_status(fresh_db):
    from deepsupport_os.mcp.tools import update_ticket

    t = TicketRepo().create_ticket(title="t", description="d", category="Teams", priority="P2")
    tid = t["ticket_id"]

    bad = update_ticket.invoke({"ticket_id": tid, "status": "P3"})
    assert bad["ok"] is False
    assert bad["error"] == "invalid_status"
    assert TicketRepo().get_ticket(tid)["status"] == "open"
    assert TicketRepo().get_ticket(tid)["priority"] == "P2"

    ok = update_ticket.invoke({"ticket_id": tid, "priority": "P3"})
    assert ok["ok"] is True
    assert ok["ticket"]["priority"] == "P3"
    assert ok["ticket"]["status"] == "open"
