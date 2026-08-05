"""Unit tests for support_tool_guards middleware (R3-1)."""

from __future__ import annotations

import json

from deepsupport_os.harness.guard_middleware import apply_support_tool_guards


class _Req:
    def __init__(self, name: str, args: dict | None = None, *, todos=None, messages=None):
        self.tool_call = {"name": name, "args": args or {}, "id": "tc1"}
        self.state = {"todos": todos or [], "messages": messages or []}


def test_blocks_tools_before_todos():
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    out = apply_support_tool_guards(_Req("get_employee", {"email": "a@b.c"}), handler)
    assert called["n"] == 0
    payload = json.loads(out.content)
    assert payload["error"] == "todos_required"


def test_allows_write_todos_without_plan():
    def handler(_req):
        return "planned"

    assert apply_support_tool_guards(_Req("write_todos", {"todos": []}), handler) == "planned"


def test_blocks_write_without_policy_check():
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _Req(
            "close_ticket",
            {"ticket_id": "T1", "resolution": "x"},
            todos=[{"content": "plan"}],
            messages=[],
        ),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "policy_check_required"


def test_allows_write_after_policy_tool_seen():
    class _ToolMsg:
        type = "tool"
        name = "check_action_permission"
        content = "{}"

    def handler(_req):
        return "ran"

    out = apply_support_tool_guards(
        _Req(
            "close_ticket",
            {"ticket_id": "T1", "resolution": "x"},
            todos=[{"content": "plan"}],
            messages=[_ToolMsg()],
        ),
        handler,
    )
    assert out == "ran"
