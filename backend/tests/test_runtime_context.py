"""R2-5: audit contextvars bind thread_id / task_id."""

from __future__ import annotations

import contextvars

from deepsupport_os.db.repositories import list_audit, write_audit
from deepsupport_os.harness.runtime_context import (
    get_task_id,
    get_thread_id,
    reset_run_context,
    run_context,
    set_run_context,
)


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


def test_reset_run_context_tolerates_foreign_context_token():
    """SSE threadpool hops create tokens in a different Context than reset."""
    tokens = set_run_context(thread_id="thr-x", task_id="task-x")

    def _reset() -> None:
        reset_run_context(tokens)

    contextvars.Context().run(_reset)  # must not raise ValueError


def test_rebind_after_yield_keeps_run_context_visible():
    """Simulate EventSourceResponse advancing a sync generator across contexts."""

    def gen():
        set_run_context(thread_id="thr-y", task_id="task-y")
        yield "a"
        set_run_context(thread_id="thr-y", task_id="task-y")
        assert get_thread_id() == "thr-y"
        assert get_task_id("adhoc") == "task-y"
        yield "b"

    it = gen()
    assert next(it) == "a"

    def resume() -> str:
        return next(it)

    assert contextvars.Context().run(resume) == "b"
