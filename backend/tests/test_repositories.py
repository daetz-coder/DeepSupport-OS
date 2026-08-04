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


def test_update_ticket_blocks_terminal_without_hitl(fresh_db):
    t = TicketRepo().create_ticket(title="t", description="d", category="Account")
    blocked = TicketRepo().update_ticket(t["ticket_id"], status="closed")
    assert blocked["error"] == "terminal_status_requires_hitl"
    closed = TicketRepo().update_ticket(
        t["ticket_id"], allow_terminal=True, status="closed", resolution="done"
    )
    assert closed["status"] == "closed"
