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


class _ToolResult:
    def __init__(self, name: str, content: str = "{}"):
        self.type = "tool"
        self.name = name
        self.content = content


def test_blocks_write_without_policy_check():
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _Req(
            "close_ticket",
            {"ticket_id": "T1", "resolution": "x"},
            todos=[{"content": "plan"}],
            messages=[_ToolResult("get_ticket")],
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
        messages=[_ToolResult("get_ticket"), *messages],
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


def test_blocks_write_without_diagnosis():
    """Password reset must not run (or HITL) before account diagnosis."""
    def handler(_req):
        return "should-not-run"

    out = apply_support_tool_guards(
        _Req(
            "request_password_reset",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "plan"}],
            messages=[
                _PolicyMsg({"action": "password_reset", "approval_required": True}),
            ],
        ),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "diagnosis_required"


def test_allows_write_after_account_diagnosis_and_policy():
    def handler(_req):
        return "ran"

    out = apply_support_tool_guards(
        _Req(
            "request_password_reset",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "plan"}],
            messages=[
                _ToolResult("get_account_status"),
                _PolicyMsg({"action": "password_reset", "approval_required": True}),
            ],
        ),
        handler,
    )
    assert out == "ran"


class _AIMsg:
    def __init__(self, tool_calls: list[dict]):
        self.type = "ai"
        self.tool_calls = tool_calls
        self.content = ""


def test_subagent_budget_blocks_duplicate_get_document():
    from deepsupport_os.harness.guard_middleware import apply_subagent_tool_budget

    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    prior = [
        _AIMsg(
            [
                {
                    "name": "get_document",
                    "args": {"document_id": "upload_outlook-login"},
                    "id": "1",
                }
            ]
        )
    ]
    out = apply_subagent_tool_budget(
        _Req("get_document", {"document_id": "upload_outlook-login"}, messages=prior),
        handler,
    )
    assert called["n"] == 0
    payload = json.loads(out.content)
    assert payload["error"] == "duplicate_tool_call"


def test_subagent_budget_blocks_after_three_calls():
    from deepsupport_os.harness.guard_middleware import apply_subagent_tool_budget

    def handler(_req):
        return "should-not-run"

    prior = [
        _AIMsg([{"name": "search_docs", "args": {"query": "a"}, "id": "1"}]),
        _AIMsg([{"name": "get_document", "args": {"document_id": "d1"}, "id": "2"}]),
        _AIMsg([{"name": "search_cases", "args": {"query": "b"}, "id": "3"}]),
    ]
    out = apply_subagent_tool_budget(
        _Req("get_document", {"document_id": "d2"}, messages=prior),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "subagent_tool_budget_exhausted"
    assert payload["max_calls"] == 3


def test_main_agent_blocks_duplicate_tool_call():
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    prior = [
        _AIMsg(
            [
                {
                    "name": "get_account_status",
                    "args": {"email": "wei.zhang@contoso.com"},
                    "id": "1",
                }
            ]
        )
    ]
    out = apply_support_tool_guards(
        _Req(
            "get_account_status",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "diag", "status": "in_progress"}],
            messages=prior,
        ),
        handler,
    )
    assert called["n"] == 0
    payload = json.loads(out.content)
    assert payload["error"] == "duplicate_tool_call"


def test_main_agent_blocks_after_tool_budget():
    def handler(_req):
        return "should-not-run"

    prior = [
        _AIMsg([{"name": f"tool_{i}", "args": {"i": i}, "id": str(i)}])
        for i in range(3)
    ]
    out = apply_support_tool_guards(
        _Req(
            "get_employee",
            {"email": "a@b.c"},
            todos=[{"content": "diag", "status": "in_progress"}],
            messages=prior,
        ),
        handler,
        max_calls=3,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "main_tool_budget_exhausted"
    assert payload["max_calls"] == 3
    assert payload["used_calls"] == 3
