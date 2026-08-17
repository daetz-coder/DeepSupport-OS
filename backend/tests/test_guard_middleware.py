"""Regression: tool dedupe must not treat the current call as its own duplicate."""

from __future__ import annotations

import json

from deepsupport_os.harness.guard_middleware import (
    apply_subagent_tool_budget,
    apply_support_tool_guards,
)


class _Req:
    def __init__(self, name: str, args: dict | None = None, *, todos=None, messages=None, id="tc1"):
        self.tool_call = {"name": name, "args": args or {}, "id": id}
        self.state = {"todos": todos or [], "messages": messages or []}


class _Human:
    type = "human"
    content = "outlook login broken"


class _AIMsg:
    def __init__(self, tool_calls: list[dict]):
        self.type = "ai"
        self.tool_calls = tool_calls
        self.content = ""


class _ToolResult:
    def __init__(self, name: str, content: str = "{}", *, tool_call_id: str = "", status: str | None = None):
        self.type = "tool"
        self.name = name
        self.content = content
        self.tool_call_id = tool_call_id
        if status is not None:
            self.status = status


def test_main_allows_call_when_aimessage_contains_self():
    """Production state already includes the AIMessage with this tool_call."""
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    tc = {
        "name": "get_account_status",
        "args": {"email": "wei.zhang@contoso.com"},
        "id": "tc-self",
    }
    messages = [_Human(), _AIMsg([tc])]
    out = apply_support_tool_guards(
        _Req(
            "get_account_status",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "diag"}],
            messages=messages,
            id="tc-self",
        ),
        handler,
    )
    assert out == "ok"
    assert called["n"] == 1


def test_main_blocks_true_duplicate_after_success():
    def handler(_req):
        return "should-not-run"

    prior_tc = {
        "name": "get_account_status",
        "args": {"email": "wei.zhang@contoso.com"},
        "id": "tc-old",
    }
    messages = [
        _Human(),
        _AIMsg([prior_tc]),
        _ToolResult("get_account_status", '{"status":"locked"}', tool_call_id="tc-old"),
        _AIMsg(
            [
                {
                    "name": "get_account_status",
                    "args": {"email": "wei.zhang@contoso.com"},
                    "id": "tc-new",
                }
            ]
        ),
    ]
    out = apply_support_tool_guards(
        _Req(
            "get_account_status",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "diag"}],
            messages=messages,
            id="tc-new",
        ),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "duplicate_tool_call"


def test_main_allows_retry_after_error_toolmessage():
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    prior_tc = {
        "name": "get_account_status",
        "args": {"email": "wei.zhang@contoso.com"},
        "id": "tc-fail",
    }
    messages = [
        _Human(),
        _AIMsg([prior_tc]),
        _ToolResult(
            "get_account_status",
            '{"error":"todos_required"}',
            tool_call_id="tc-fail",
            status="error",
        ),
        _AIMsg(
            [
                {
                    "name": "get_account_status",
                    "args": {"email": "wei.zhang@contoso.com"},
                    "id": "tc-retry",
                }
            ]
        ),
    ]
    out = apply_support_tool_guards(
        _Req(
            "get_account_status",
            {"email": "wei.zhang@contoso.com"},
            todos=[{"content": "diag"}],
            messages=messages,
            id="tc-retry",
        ),
        handler,
    )
    assert out == "ok"
    assert called["n"] == 1


def test_main_budget_ignores_prior_turn():
    def handler(_req):
        return "ok"

    old = [_AIMsg([{"name": f"t{i}", "args": {"i": i}, "id": f"old{i}"}]) for i in range(5)]
    messages = [*old, _Human(), _AIMsg([{"name": "get_employee", "args": {"email": "a@b.c"}, "id": "n1"}])]
    out = apply_support_tool_guards(
        _Req(
            "get_employee",
            {"email": "a@b.c"},
            todos=[{"content": "diag"}],
            messages=messages,
            id="n1",
        ),
        handler,
        max_calls=3,
    )
    assert out == "ok"


def test_subagent_allows_call_when_aimessage_contains_self():
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    tc = {"name": "search_docs", "args": {"query": "outlook"}, "id": "s1"}
    out = apply_subagent_tool_budget(
        _Req("search_docs", {"query": "outlook"}, messages=[_AIMsg([tc])], id="s1"),
        handler,
    )
    assert out == "ok"
    assert called["n"] == 1


def test_subagent_fs_tools_do_not_burn_budget():
    def handler(_req):
        return "ok"

    prior = [
        _AIMsg([{"name": "read_file", "args": {"path": "/skills/x/SKILL.md"}, "id": "r1"}]),
        _AIMsg([{"name": "read_file", "args": {"path": "/skills/y/SKILL.md"}, "id": "r2"}]),
        _AIMsg([{"name": "read_file", "args": {"path": "/skills/z/SKILL.md"}, "id": "r3"}]),
    ]
    out = apply_subagent_tool_budget(
        _Req(
            "search_docs",
            {"query": "outlook"},
            messages=[
                *prior,
                _AIMsg([{"name": "search_docs", "args": {"query": "outlook"}, "id": "s1"}]),
            ],
            id="s1",
        ),
        handler,
        max_calls=3,
    )
    assert out == "ok"


def test_subagent_budget_blocks_business_tools_only():
    def handler(_req):
        return "should-not-run"

    prior = [
        _AIMsg([{"name": "search_docs", "args": {"query": "a"}, "id": "1"}]),
        _AIMsg([{"name": "get_document", "args": {"document_id": "d1"}, "id": "2"}]),
        _AIMsg([{"name": "search_cases", "args": {"query": "b"}, "id": "3"}]),
    ]
    out = apply_subagent_tool_budget(
        _Req(
            "get_document",
            {"document_id": "d2"},
            messages=[
                *prior,
                _AIMsg([{"name": "get_document", "args": {"document_id": "d2"}, "id": "4"}]),
            ],
            id="4",
        ),
        handler,
        max_calls=3,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "subagent_tool_budget_exhausted"
    assert payload["used_calls"] == 3


def test_ask_user_allows_when_aimessage_contains_self():
    """First ask_user must not treat its own tool_call as a prior duplicate."""
    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return "ok"

    q = "登录 Outlook 时具体看到什么提示？"
    tc = {"name": "ask_user", "args": {"question": q}, "id": "ask-1"}
    messages = [_Human(), _AIMsg([tc])]
    out = apply_support_tool_guards(
        _Req("ask_user", {"question": q}, todos=[{"content": "ask"}], messages=messages, id="ask-1"),
        handler,
    )
    assert out == "ok"
    assert called["n"] == 1


def test_ask_user_blocks_true_duplicate_after_answer():
    def handler(_req):
        return "should-not-run"

    q = "登录 Outlook 时具体看到什么提示？"
    prior = {"name": "ask_user", "args": {"question": q}, "id": "ask-old"}
    messages = [
        _Human(),
        _AIMsg([prior]),
        _ToolResult("ask_user", "反复弹出凭据框", tool_call_id="ask-old"),
        _AIMsg([{"name": "ask_user", "args": {"question": q}, "id": "ask-new"}]),
    ]
    out = apply_support_tool_guards(
        _Req(
            "ask_user",
            {"question": q},
            todos=[{"content": "ask"}],
            messages=messages,
            id="ask-new",
        ),
        handler,
    )
    payload = json.loads(out.content)
    assert payload["error"] == "ask_user_duplicate"
