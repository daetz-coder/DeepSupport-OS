"""Unit tests for nested subagent progress callbacks."""

from __future__ import annotations

import queue
from uuid import uuid4

from deepsupport_os.api.subagent_progress import SubagentProgressHandler


def test_nested_tools_emit_progress_while_task_open():
    bus: queue.Queue = queue.Queue()
    h = SubagentProgressHandler(bus)
    rid = uuid4()

    h.on_tool_start(
        {"name": "task"},
        "",
        run_id=rid,
        inputs={"subagent_type": "environment-diagnosis", "description": "diagnose"},
    )
    assert bus.empty()  # dispatch itself is handled by parent SSE

    h.on_tool_start(
        {"name": "get_employee"},
        "",
        run_id=uuid4(),
        parent_run_id=rid,
        inputs={"email": "wei.zhang@contoso.com"},
        metadata={"ls_agent_type": "subagent"},
    )
    kind, payload = bus.get_nowait()
    assert kind == "progress"
    assert payload["phase"] == "tool_start"
    assert payload["name"] == "get_employee"
    assert payload["subagent"] == "environment-diagnosis"

    h.on_tool_end(
        {"ok": True},
        run_id=uuid4(),
        parent_run_id=rid,
        name="get_employee",
        metadata={"ls_agent_type": "subagent"},
    )
    kind, payload = bus.get_nowait()
    assert kind == "progress"
    assert payload["phase"] == "tool_end"
    assert payload["name"] == "get_employee"

    h.on_tool_end("done", run_id=rid, name="task")
    assert bus.empty()


def test_main_agent_tools_do_not_emit_without_subagent_context():
    bus: queue.Queue = queue.Queue()
    h = SubagentProgressHandler(bus)
    h.on_tool_start(
        {"name": "write_todos"},
        "",
        run_id=uuid4(),
        inputs={"todos": []},
    )
    assert bus.empty()
