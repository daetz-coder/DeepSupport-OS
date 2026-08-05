from deepsupport_os.harness.run_overview import (
    annotate_steps,
    build_run_overview,
    skill_from_path,
    slice_current_run_steps,
)
from deepsupport_os.harness.tool_provenance import (
    clear_tool_provenance,
    lookup_tool_provenance,
    register_tool_provenance,
)


def test_skill_from_virtual_path():
    assert skill_from_path("/skills/outlook-troubleshoot/SKILL.md") == "outlook-troubleshoot"
    assert skill_from_path("/skills/imported/foo/references/a.md") == "foo"
    assert skill_from_path("/workspace/x/diagnosis.md") is None


def test_annotate_skill_and_stage():
    clear_tool_provenance()
    register_tool_provenance("get_employee", source="local")
    register_tool_provenance("search_docs", source="knowledge")
    steps = [
        {"kind": "tool_call", "name": "write_todos", "args": {}},
        {"kind": "tool_call", "name": "get_employee", "args": {"email": "a@b.com"}},
        {
            "kind": "tool_call",
            "name": "read_file",
            "args": {"file_path": "/skills/outlook-troubleshoot/SKILL.md"},
        },
        {"kind": "tool_call", "name": "search_docs", "args": {"query": "lock"}},
        {"kind": "subagent_dispatch", "name": "task", "subagent": "knowledge-research"},
        {
            "kind": "context_offload",
            "name": "write_file",
            "offload_path": "/workspace/t/diagnosis.md",
            "args": {"file_path": "/workspace/t/diagnosis.md"},
        },
    ]
    annotated = annotate_steps(steps)
    assert annotated[0]["stage"] == "plan"
    assert annotated[1]["stage"] == "diagnose"
    assert annotated[1]["tool_source"] == "local"
    assert annotated[2]["skill_used"] == "outlook-troubleshoot"
    assert annotated[2]["stage"] == "research"
    assert annotated[3]["tool_source"] == "knowledge"
    assert annotated[4]["stage"] == "research"
    assert annotated[5]["stage"] == "action"


def test_build_run_overview_counts():
    clear_tool_provenance()
    register_tool_provenance("get_employee", source="local")
    steps = [
        {"kind": "tool_call", "name": "get_employee", "args": {}},
        {"kind": "tool_call", "name": "get_employee", "args": {}},
        {
            "kind": "tool_call",
            "name": "read_file",
            "args": {"file_path": "/skills/teams-voip/SKILL.md"},
        },
        {"kind": "subagent_dispatch", "name": "task", "subagent": "environment-diagnosis"},
    ]
    overview = build_run_overview(
        steps,
        todos=[{"content": "a", "status": "completed"}, {"content": "b", "status": "pending"}],
        metrics={"duration_ms": 12.5},
        status="completed",
    )
    assert overview["tools"]["total_calls"] >= 3
    assert "environment-diagnosis" in overview["agents"]
    assert "teams-voip" in overview["skills"]
    assert overview["plan"]["completed"] == 1
    assert any(s["id"] == "diagnose" for s in overview["stages"])
    assert lookup_tool_provenance("get_employee")["source"] == "local"


def test_current_run_slice_ignores_prior_turn():
    steps = [
        {"kind": "user", "content": "first"},
        {"kind": "tool_call", "name": "get_employee", "args": {}},
        {"kind": "tool_call", "name": "create_ticket", "args": {}},
        {"kind": "assistant", "content": "done"},
        {"kind": "user", "content": "仍无法解决"},
        {"kind": "tool_call", "name": "ask_user", "args": {"question": "哪几步？"}},
    ]
    scoped = slice_current_run_steps(steps)
    assert scoped[0]["content"] == "仍无法解决"
    assert all(s.get("name") != "create_ticket" for s in scoped)
    overview = build_run_overview(steps, current_run_only=True)
    assert overview["scope"] == "current_run"
    names = [t["name"] for t in overview["tools"]["items"]]
    assert "ask_user" in names
    assert "create_ticket" not in names
    full = build_run_overview(steps, current_run_only=False)
    assert full["scope"] == "full_thread"
    full_names = [t["name"] for t in full["tools"]["items"]]
    assert "create_ticket" in full_names
    assert "ask_user" in full_names


def test_tool_result_inherits_stage_not_orphaned_in_other():
    """tool_result without args must follow its call — not inflate「其他」with 0 tools."""
    clear_tool_provenance()
    steps = [
        {
            "kind": "tool_call",
            "name": "read_file",
            "args": {"file_path": "/skills/outlook-troubleshooting/SKILL.md"},
        },
        {"kind": "tool_result", "name": "read_file", "content": "---\nname: outlook"},
        {
            "kind": "subagent_dispatch",
            "name": "task",
            "subagent": "knowledge-research",
        },
        {"kind": "tool_result", "name": "task", "content": "report"},
    ]
    annotated = annotate_steps(steps)
    assert annotated[0]["stage"] == "research"
    assert annotated[1]["skill_used"] == "outlook-troubleshooting"
    assert annotated[1]["stage"] == "research"
    assert annotated[2]["stage"] == "research"
    assert annotated[3]["subagent"] == "knowledge-research"
    assert annotated[3]["stage"] == "research"

    overview = build_run_overview(steps, current_run_only=False)
    by_id = {s["id"]: s for s in overview["stages"]}
    assert "other" not in by_id
    research = by_id["research"]
    assert research["tool_count"] == 2  # read_file call + task dispatch
    assert "outlook-troubleshooting" in research["summary"] or "read_file" in research["summary"]
    assert "knowledge-research" in research["summary"]
