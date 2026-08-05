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


class _PolicyMsg:
    """Fake ToolMessage carrying a check_action_permission result payload."""

    def __init__(self, payload: dict):
        self.type = "tool"
        self.name = "check_action_permission"
        self.content = json.dumps(payload, ensure_ascii=False)


def _req_close(messages):
    return _Req(
        "close_ticket",
        {"ticket_id": "T1", "resolution": "x"},
        todos=[{"content": "plan"}],
        messages=messages,
    )


def test_allows_write_after_passing_policy_check():
    """A found entry for THIS action passes the gate (AR-15 / R3-1)."""
    def handler(_req):
        return "ran"

    out = apply_support_tool_guards(
        _req_close([_PolicyMsg({"action": "close_ticket", "approval_required": True, "sla_hours": 24})]),
        handler,
    )
    assert out == "ran"


def test_blocks_write_when_policy_not_found():
    """policy_not_found / error payloads must NOT satisfy the gate."""
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _req_close([_PolicyMsg({"error": "policy_not_found"})]),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "policy_check_required"


def test_blocks_write_when_different_action_checked():
    """Checking an unrelated (read-only) action must not gate a write tool."""
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _req_close([_PolicyMsg({"action": "read_employee", "approval_required": False})]),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "policy_check_required"
    assert payload["required_policy_action"] == "close_ticket"


def test_blocks_write_when_another_write_action_checked():
    """A password_reset policy cannot gate close_ticket."""
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _req_close([_PolicyMsg({"action": "password_reset", "approval_required": True})]),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "policy_check_required"
