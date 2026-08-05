"""Unit tests for extended eval metrics aggregation."""

from __future__ import annotations

from deepsupport_os.harness.eval_metrics import (
    aggregate_summary,
    enrich_ok,
    metrics_catalog,
    score_trace_extras,
)


def test_metrics_catalog_covers_extended_keys():
    keys = {m["key"] for m in metrics_catalog()}
    for required in (
        "pass_rate",
        "skill_hit_rate",
        "subagent_hit_rate",
        "planning_hit_rate",
        "write_safety_rate",
        "grounding_rate",
        "long_task_pass_rate",
        "p50_elapsed_ms",
        "p95_elapsed_ms",
        "by_tag",
        "avg_tool_calls",
    ):
        assert required in keys


def test_score_trace_extras_and_aggregate():
    case = {
        "id": "demo",
        "tags": ["long-task", "hitl"],
        "expect": {
            "tools": ["get_account_status"],
            "hitl": ["request_password_reset"],
            "skills": ["outlook-troubleshooting"],
            "subagents": ["environment-diagnosis"],
            "planning": True,
        },
    }
    steps = [
        {"kind": "tool_call", "name": "write_todos", "args": {}},
        {
            "kind": "tool_call",
            "name": "read_file",
            "args": {"file_path": "/skills/outlook-troubleshooting/SKILL.md"},
            "skill_used": "outlook-troubleshooting",
        },
        {
            "kind": "subagent_dispatch",
            "name": "task",
            "subagent": "environment-diagnosis",
            "args": {},
        },
        {"kind": "tool_call", "name": "get_account_status", "args": {}},
        {"kind": "tool_call", "name": "request_password_reset", "args": {}},
    ]
    extras = score_trace_extras(
        case,
        tools_seen={"write_todos", "read_file", "task", "get_account_status", "request_password_reset"},
        pending={"request_password_reset"},
        subagents=["environment-diagnosis"],
        skills_seen=["outlook-troubleshooting"],
        steps=steps,
        tool_hit=True,
    )
    assert extras["skill_hit"] is True
    assert extras["subagent_hit"] is True
    assert extras["planning_hit"] is True
    assert extras["write_safety_hit"] is True

    row = {
        "id": "demo",
        "ok": enrich_ok(True, extras, case),
        "mode": "online",
        "elapsed_ms": 1200,
        "tool_hit": True,
        "hitl_hit": True,
        "offload_hit": True,
        "expect_hitl": True,
        "expect_skills": True,
        "expect_subagents": True,
        "expect_grounding": False,
        "tags": ["long-task", "hitl"],
        **extras,
    }
    unsafe = {
        **row,
        "id": "bad",
        "ok": False,
        "write_safety_hit": False,
        "elapsed_ms": 800,
        "tags": ["ticket"],
    }
    summary = aggregate_summary([row, unsafe], mode="online", use_daytona=False)
    assert summary["total"] == 2
    assert summary["pass_rate"] == 0.5
    assert summary["skill_hit_rate"] == 1.0
    assert summary["subagent_hit_rate"] == 1.0
    assert summary["planning_hit_rate"] == 1.0
    assert summary["p50_elapsed_ms"] is not None
    assert summary["p95_elapsed_ms"] is not None
    assert "long-task" in summary["by_tag"]
    assert summary["avg_tool_calls"] is not None
