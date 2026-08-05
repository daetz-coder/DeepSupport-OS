"""R3-5: WriteUnitOfWork + OTel span helpers."""

from __future__ import annotations

from deepsupport_os.db.repositories import AccountRepo
from deepsupport_os.harness.runtime_context import run_context
from deepsupport_os.harness.tracing import span
from deepsupport_os.harness.unit_of_work import WriteUnitOfWork


def test_write_uow_applies_and_is_idempotent(fresh_db):
    email = "wei.zhang@contoso.com"
    pending = [{"name": "request_password_reset", "args": {"email": email}}]
    with run_context(thread_id="uow-t1", task_id="uow-1"):
        uow = WriteUnitOfWork(approval_id="uow-1", task_id="uow-1", thread_id="uow-t1")
        first = uow.run(pending)
    assert first and first[0]["result"].get("ok")
    assert AccountRepo().get_account_status(email)["status"] == "active"
    assert not uow.failed

    uow2 = WriteUnitOfWork(approval_id="uow-2", task_id="uow-2", thread_id="uow-t1")
    second = uow2.run(pending)
    assert second[0]["result"].get("already_applied") is True


def test_span_context_no_raise():
    with span("test.noop", foo="bar") as s:
        # May be None if OTel missing; must not raise either way.
        _ = s
