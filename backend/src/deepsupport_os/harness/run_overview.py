"""Stage grouping + run overview stats for the support console."""

from __future__ import annotations

import json
import re
from typing import Any

from deepsupport_os.harness.tool_provenance import lookup_tool_provenance

_SKILL_PATH_RE = re.compile(r"/skills/(?:imported/)?([^/]+)/", re.I)

STAGE_DEFS = (
    ("plan", "理解与规划"),
    ("diagnose", "环境诊断"),
    ("research", "知识检索"),
    ("action", "方案与写操作"),
    ("other", "其他"),
)

PLAN_TOOLS = {"write_todos", "read_todos"}
DIAGNOSE_TOOLS = {
    "get_employee",
    "get_department",
    "get_manager",
    "get_device",
    "list_user_devices",
    "get_account_status",
    "get_license",
    "check_action_permission",
}
RESEARCH_TOOLS = {
    "search_docs",
    "search_cases",
    "search_knowledge",
    "search_similar_cases",
}
ACTION_TOOLS = {
    "ask_user",
    "request_password_reset",
    "request_license_change",
    "close_ticket",
    "escalate_ticket",
    "create_ticket",
    "update_ticket",
    "get_ticket",
    "notify_user",
    "run_sandbox_shell",
}
WRITE_FILE_TOOLS = {"write_file", "edit_file"}


def _args_dict(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _path_from_args(args: Any) -> str:
    d = _args_dict(args)
    return str(d.get("file_path") or d.get("path") or d.get("filename") or "")


def skill_from_path(path: str) -> str | None:
    m = _SKILL_PATH_RE.search(path.replace("\\", "/"))
    return m.group(1) if m else None


def classify_stage(step: dict[str, Any]) -> str:
    kind = step.get("kind")
    name = str(step.get("name") or "")
    if kind == "subagent_dispatch":
        sub = str(step.get("subagent") or "")
        if sub == "environment-diagnosis":
            return "diagnose"
        if sub == "knowledge-research":
            return "research"
        if sub == "ticket-operations":
            return "action"
        return "plan"
    if kind == "context_offload":
        return "action"
    if name in PLAN_TOOLS or (kind == "assistant" and not name):
        return "plan"
    if name in DIAGNOSE_TOOLS:
        return "diagnose"
    if name in RESEARCH_TOOLS or step.get("skill_used"):
        return "research"
    if name in ACTION_TOOLS or name in WRITE_FILE_TOOLS:
        return "action"
    if kind in {"user", "assistant"}:
        return "plan"
    return "other"


def annotate_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutate/copy steps with skill_used, tool_source, stage."""
    out: list[dict[str, Any]] = []
    for raw in steps:
        step = dict(raw)
        name = str(step.get("name") or "")
        args = step.get("args")
        path = _path_from_args(args) if name in {"read_file", "write_file", "edit_file"} else ""
        if not path and step.get("offload_path"):
            path = str(step["offload_path"])
        skill = skill_from_path(path) if path else None
        if skill:
            step["skill_used"] = skill
        if name and step.get("kind") in {
            "tool_call",
            "tool_result",
            "subagent_dispatch",
            "context_offload",
        }:
            prov = lookup_tool_provenance(name)
            step["tool_source"] = prov.get("source")
            if prov.get("server"):
                step["mcp_server"] = prov["server"]
        step["stage"] = classify_stage(step)
        out.append(step)
    return out


def group_stages(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group annotated steps into ordered stage buckets (non-empty only)."""
    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k, _ in STAGE_DEFS}
    for step in steps:
        key = str(step.get("stage") or "other")
        if key not in buckets:
            key = "other"
        buckets[key].append(step)

    stages: list[dict[str, Any]] = []
    for key, label in STAGE_DEFS:
        items = buckets[key]
        if not items:
            continue
        toolish = [
            s
            for s in items
            if s.get("kind") in {"tool_call", "subagent_dispatch", "context_offload", "tool_result"}
        ]
        status = "done"
        if any(s.get("name") == "ask_user" for s in items):
            # ask without following tool_result still pending visually handled by interrupt
            status = "done"
        stages.append(
            {
                "id": key,
                "label": label,
                "status": status,
                "step_count": len(items),
                "tool_count": len([s for s in items if s.get("kind") == "tool_call"]),
                "steps": items,
                "summary": _stage_summary(items, toolish),
            }
        )
    return stages


def _stage_summary(items: list[dict[str, Any]], toolish: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for s in toolish:
        n = s.get("subagent") or s.get("skill_used") or s.get("name")
        if n and n not in names:
            names.append(str(n))
        if len(names) >= 4:
            break
    if names:
        return " · ".join(names)
    if any(s.get("kind") == "assistant" for s in items):
        return "助手回复"
    return f"{len(items)} 步"


def slice_current_run_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep steps from the last user message onward (= current conversation turn)."""
    if not steps:
        return []
    last_user = -1
    for i, s in enumerate(steps):
        if s.get("kind") == "user":
            last_user = i
    if last_user < 0:
        return list(steps)
    return list(steps[last_user:])


def build_run_overview(
    steps: list[dict[str, Any]],
    *,
    todos: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    status: str | None = None,
    current_run_only: bool = True,
) -> dict[str, Any]:
    annotated = annotate_steps(steps)
    scoped = slice_current_run_steps(annotated) if current_run_only else annotated
    stages = group_stages(scoped)

    agents: list[str] = []
    skills: list[str] = []
    tool_counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    mcp_servers: set[str] = set()

    for s in scoped:
        kind = s.get("kind")
        if kind == "subagent_dispatch":
            sub = str(s.get("subagent") or "unknown")
            if sub not in agents:
                agents.append(sub)
        if s.get("skill_used"):
            sk = str(s["skill_used"])
            if sk not in skills:
                skills.append(sk)
        if kind in {"tool_call", "subagent_dispatch", "context_offload"}:
            name = str(s.get("name") or "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1
            src = str(s.get("tool_source") or "unknown")
            sources[src] = sources.get(src, 0) + 1
            if s.get("mcp_server"):
                mcp_servers.add(str(s["mcp_server"]))

    todos = todos or []
    todo_done = sum(1 for t in todos if t.get("status") == "completed")
    tool_list = [
        {"name": n, "count": c}
        for n, c in sorted(tool_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    return {
        "status": status,
        "duration_ms": (metrics or {}).get("duration_ms"),
        "scope": "current_run" if current_run_only else "full_thread",
        "plan": {
            "total": len(todos),
            "completed": todo_done,
            "items": todos,
        },
        "stages": stages,
        "agents": agents,
        "skills": skills,
        "mcp": {
            "local_calls": sources.get("local", 0),
            "remote_calls": sources.get("remote", 0),
            "knowledge_calls": sources.get("knowledge", 0),
            "servers": sorted(mcp_servers),
            "by_source": sources,
        },
        "tools": {
            "total_calls": sum(tool_counts.values()),
            "unique": len(tool_counts),
            "items": tool_list,
        },
        "step_count": len(scoped),
        "thread_step_count": len(annotated),
    }


def enrich_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Annotate steps; attach current-run stages (plus full-thread stages_all)."""
    steps = annotate_steps(list(trace.get("steps") or []))
    trace = dict(trace)
    trace["steps"] = steps
    current = slice_current_run_steps(steps)
    trace["stages"] = group_stages(current)
    trace["stages_all"] = group_stages(steps)
    skills = sorted({s["skill_used"] for s in current if s.get("skill_used")})
    trace["skills_used"] = skills
    return trace
