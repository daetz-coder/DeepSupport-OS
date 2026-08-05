"""R2-5: audit contextvars bind thread_id / task_id."""

from __future__ import annotations

from deepsupport_os.db.repositories import list_audit, write_audit
from deepsupport_os.harness.runtime_context import run_context


def test_write_audit_picks_up_run_context(fresh_db):
    with run_context(thread_id="thr-1", task_id="task-1"):
        write_audit(tool="get_employee", arguments={"email": "a@b.c"}, result={"ok": True})

    rows = list_audit(limit=5, thread_id="thr-1")
    assert rows
    assert rows[-1]["task_id"] == "task-1"
    assert rows[-1]["thread_id"] == "thr-1"
    assert rows[-1]["tool"] == "get_employee"

    other = list_audit(limit=5, thread_id="thr-other")
    assert other == []
