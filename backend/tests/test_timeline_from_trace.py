"""Timeline tree should nest subagent tools and surface skills."""

from __future__ import annotations

from deepsupport_os.harness.timeline_from_trace import build_timeline_tree_from_steps


def _flatten(node: dict) -> list[dict]:
    out = [node]
    for c in node.get("children") or []:
        out.extend(_flatten(c))
    return out


def test_timeline_nests_tools_under_subagent():
    steps = [
        {"kind": "tool_call", "name": "write_todos", "args": {}},
        {
            "kind": "tool_call",
            "name": "task",
            "args": {"subagent_type": "environment-diagnosis"},
        },
        {
            "kind": "tool_call",
            "name": "get_account_status",
            "args": {"email": "a@b.c"},
        },
        {
            "kind": "tool_call",
            "name": "read_file",
            "args": {"file_path": "/skills/account-access/SKILL.md"},
        },
        {"kind": "tool_result", "name": "task", "content": "ok"},
        {"kind": "tool_call", "name": "check_action_permission", "args": {"action": "x"}},
    ]
    tree = build_timeline_tree_from_steps(steps, task_id="t1", duration_ms=1000)
    assert tree["name"] == "main_agent"
    # top-level: write_todos, environment-diagnosis, check_action_permission
    top = [c["name"] for c in tree["children"]]
    assert "write_todos" in top
    assert "environment-diagnosis" in top
    assert "check_action_permission" in top
    assert "get_account_status" not in top  # nested, not sibling

    env = next(c for c in tree["children"] if c["name"] == "environment-diagnosis")
    nested = {c["name"] for c in env["children"]}
    assert "get_account_status" in nested
    assert "account-access" in nested  # skill span


def test_timeline_includes_explicit_subagent_tag():
    steps = [
        {
            "kind": "subagent_dispatch",
            "name": "task",
            "subagent": "knowledge-research",
            "args": {"subagent_type": "knowledge-research"},
        },
        {
            "kind": "tool_call",
            "name": "search_docs",
            "subagent": "knowledge-research",
            "args": {"query": "outlook"},
        },
    ]
    tree = build_timeline_tree_from_steps(steps)
    kr = next(c for c in tree["children"] if c["name"] == "knowledge-research")
    assert any(c["name"] == "search_docs" for c in kr["children"])
