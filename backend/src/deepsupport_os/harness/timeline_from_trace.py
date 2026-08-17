"""Build execution-timeline trees from persisted trace steps (source of truth)."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from deepsupport_os.harness.run_overview import annotate_steps, skill_from_path


def _args_path(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    return str(args.get("file_path") or args.get("path") or args.get("filename") or "")


def _node(
    *,
    name: str,
    kind: str,
    parent_id: str | None,
    status: str = "completed",
    start_time: float,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nid = str(uuid4())
    end = start_time + ((duration_ms or 0) / 1000.0)
    return {
        "id": nid,
        "name": name,
        "kind": kind,
        "parent_id": parent_id,
        "start_time": start_time,
        "end_time": end if duration_ms is not None else start_time,
        "duration_ms": duration_ms,
        "status": status,
        "metadata": metadata or {},
        "children": children or [],
    }


def _count_descendants(node: dict[str, Any]) -> int:
    n = 0
    for c in node.get("children") or []:
        n += 1 + _count_descendants(c)
    return n


def build_timeline_tree_from_steps(
    steps: list[dict[str, Any]] | None,
    *,
    task_id: str = "",
    status: str = "completed",
    duration_ms: float | None = None,
    start_time: float | None = None,
) -> dict[str, Any]:
    """Hierarchical timeline: subagent scopes contain their tools/skills."""
    annotated = annotate_steps(list(steps or []))
    t0 = float(start_time if start_time is not None else time.time())
    root = _node(
        name="main_agent",
        kind="agent",
        parent_id=None,
        status=status or "completed",
        start_time=t0,
        duration_ms=float(duration_ms) if duration_ms is not None else None,
        metadata={"task_id": task_id, "source": "trace"},
    )
    root_id = root["id"]

    sub_nodes: dict[str, dict[str, Any]] = {}
    # Stack of active subagent names for nesting until matching task tool_result.
    active: list[str] = []
    cursor = t0
    step_ms = 1.0

    def _ensure_sub(sub: str, args: dict[str, Any], *, from_kind: str) -> dict[str, Any]:
        if sub not in sub_nodes:
            node = _node(
                name=sub,
                kind="subagent",
                parent_id=root_id,
                status="completed",
                start_time=cursor,
                duration_ms=step_ms,
                metadata={"args": args, "from": from_kind},
            )
            sub_nodes[sub] = node
            root["children"].append(node)
        return sub_nodes[sub]

    for step in annotated:
        kind = str(step.get("kind") or "")
        name = str(step.get("name") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}

        # Close subagent scope when parent sees task tool_result.
        if kind == "tool_result" and name == "task":
            if active:
                active.pop()
            continue

        if kind not in {"tool_call", "subagent_dispatch", "context_offload"}:
            continue
        if not name and kind != "subagent_dispatch":
            continue

        sub = str(step.get("subagent") or "").strip()
        if kind == "subagent_dispatch" or name == "task":
            sub = sub or str(
                (args or {}).get("subagent_type")
                or (args or {}).get("name")
                or (args or {}).get("agent")
                or "subagent"
            )
            _ensure_sub(sub, args or {}, from_kind=kind)
            if not active or active[-1] != sub:
                active.append(sub)
            cursor += step_ms / 1000.0
            continue

        # Prefer explicit subagent tag; else nest under currently open task scope.
        if not sub and active:
            sub = active[-1]
        if sub:
            parent_node = _ensure_sub(sub, {}, from_kind="inherit")
            parent_id = parent_node["id"]
            parent_children = parent_node["children"]
        else:
            parent_id = root_id
            parent_children = root["children"]

        path = _args_path(args)
        skill = step.get("skill_used") or skill_from_path(path)
        # Skill reads become skill spans; other tools stay tools (optionally tagged).
        if skill and name in {"read_file", "write_file", "edit_file", "ls", "glob", "grep"}:
            span_kind = "skill"
            span_name = str(skill)
        else:
            span_kind = "tool"
            span_name = name

        child = _node(
            name=span_name,
            kind=span_kind,
            parent_id=parent_id,
            status="completed",
            start_time=cursor,
            duration_ms=step_ms,
            metadata={
                "tool": name,
                "args": args,
                "subagent": sub or None,
                "skill_used": skill,
            },
        )
        parent_children.append(child)
        cursor += step_ms / 1000.0

    if root["duration_ms"] is None and root["children"]:
        root["duration_ms"] = max(1.0, (cursor - t0) * 1000.0)
        root["end_time"] = cursor

    return root


def prefer_richer_timeline(
    primary: dict[str, Any] | None,
    fallback: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Pick the tree with more nested activity (live tracker often richer mid-run)."""
    if primary and not fallback:
        return primary
    if fallback and not primary:
        return fallback
    if not primary and not fallback:
        return None
    assert primary is not None and fallback is not None
    if _count_descendants(fallback) > _count_descendants(primary):
        return fallback
    return primary
