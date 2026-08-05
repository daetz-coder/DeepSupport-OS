"""Offline/online evaluation for mvp_cases.jsonl.

Offline mode checks case schema + golden expect fields without calling LLM.
Online mode (optional) invokes the harness and scores tool/HITL presence.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "benchmark" / "mvp_cases.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def score_offline(case: dict[str, Any]) -> dict[str, Any]:
    expect = case.get("expect") or {}
    ok = bool(case.get("id") and case.get("question") and isinstance(expect, dict))
    checks = {
        "has_id": bool(case.get("id")),
        "has_question": bool(case.get("question")),
        "has_expect": bool(expect),
        "has_tags": bool(case.get("tags")),
    }
    return {
        "id": case.get("id"),
        "ok": ok and all(checks.values()),
        "mode": "offline",
        "checks": checks,
        "expect_keys": sorted(expect.keys()),
    }


def score_online(case: dict[str, Any], *, use_daytona: bool = False) -> dict[str, Any]:
    from deepsupport_os.api.trace import build_trace
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.db import init_db
    from deepsupport_os.db.seed import seed_database
    from deepsupport_os.harness.agent import build_support_agent
    from deepsupport_os.harness.eval_metrics import enrich_ok, score_trace_extras
    from deepsupport_os.harness.workspace import ensure_thread_workspace
    import uuid

    settings = get_settings()
    if not settings.llm_configured:
        return {"id": case.get("id"), "ok": False, "error": "llm_not_configured", "mode": "online"}

    init_db()
    seed_database(force=False)
    thread_id = str(uuid.uuid4())
    ws = ensure_thread_workspace(thread_id)
    # Local-first hybrid (skills on disk). --daytona only attaches /sandbox/ sidecar.
    agent = build_support_agent(thread_id=thread_id, use_daytona=use_daytona)
    config = {"configurable": {"thread_id": thread_id}}
    t0 = time.perf_counter()
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": case["question"]}]},
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": case.get("id"),
            "ok": False,
            "mode": "online",
            "error": str(exc),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "use_daytona": use_daytona,
            "tags": list(case.get("tags") or []),
        }
    elapsed_ms = (time.perf_counter() - t0) * 1000
    msgs = result.get("messages", [])
    trace = build_trace(msgs)
    steps = list(trace.get("steps") or [])
    tool_names = {t.get("name") for t in trace.get("tool_calls") or []}
    # Also count tool names from annotated steps (subagent_dispatch / offload keep name)
    for s in steps:
        if s.get("name") and s.get("kind") in {
            "tool_call",
            "subagent_dispatch",
            "context_offload",
        }:
            tool_names.add(s.get("name"))
    expect = case.get("expect") or {}
    required_tools = set(expect.get("tools") or [])
    hitl_tools = set(expect.get("hitl") or [])
    pending = {p.get("name") for p in (trace.get("pending_writes") or [])}
    subagents = [s.get("subagent") for s in (trace.get("subagent_dispatches") or []) if s.get("subagent")]
    skills_seen = sorted(
        {
            str(s.get("skill_used"))
            for s in steps
            if s.get("skill_used")
        }
        | set(trace.get("skills_used") or [])
    )

    tool_hit = required_tools.issubset(tool_names) if required_tools else True
    hitl_hit = hitl_tools.issubset(tool_names | pending) if hitl_tools else True

    # Weak assertion: long-task / context-offload cases should leave workspace files
    tags = set(case.get("tags") or [])
    expect_offload = bool(expect.get("workspace_files")) or (
        "context-offload" in tags or "long-task" in tags
    )
    workspace_files = sorted(p.name for p in ws.rglob("*") if p.is_file()) if ws.exists() else []
    offload_hit = True
    if expect_offload:
        required_files = set(expect.get("workspace_files") or [])
        if required_files:
            offload_hit = required_files.issubset(set(workspace_files))
        else:
            # soft: any markdown artifact or context_offload step
            offloads = trace.get("context_offloads") or []
            offload_hit = bool(workspace_files) or bool(offloads)

    extras = score_trace_extras(
        case,
        tools_seen={str(x) for x in tool_names if x},
        pending={str(x) for x in pending if x},
        subagents=[str(x) for x in subagents if x],
        skills_seen=skills_seen,
        steps=steps,
        tool_hit=tool_hit,
    )
    base_ok = tool_hit and hitl_hit and offload_hit
    ok = enrich_ok(base_ok, extras, case)
    return {
        "id": case.get("id"),
        "ok": ok,
        "mode": "online",
        "elapsed_ms": round(elapsed_ms, 1),
        "workspace_path": str(ws),
        "workspace_files": workspace_files,
        "use_daytona": use_daytona,
        "tools_seen": sorted(x for x in tool_names if x),
        "pending_writes": sorted(x for x in pending if x),
        "subagents": [x for x in subagents if x],
        "tool_hit": tool_hit,
        "hitl_hit": hitl_hit,
        "offload_hit": offload_hit,
        "expect_offload": expect_offload,
        "expect_hitl": bool(hitl_tools),
        "expect_skills": bool(expect.get("skills")),
        "expect_subagents": bool(expect.get("subagents")),
        "expect_grounding": "grounding" in tags,
        **extras,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--offline", action="store_true", default=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Load enabled cases from eval_cases table (sync from jsonl first if empty)",
    )
    parser.add_argument(
        "--daytona",
        action="store_true",
        help="Attach Daytona as /sandbox/ sidecar (Skills stay local; default offline path is local-only)",
    )
    args = parser.parse_args()

    if args.from_db:
        from deepsupport_os.db.eval_store import list_eval_cases, sync_eval_cases

        sync_eval_cases(path=args.cases)
        cases = list_eval_cases(enabled_only=True)
    else:
        cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]

    mode_online = args.online
    results = []
    for case in cases:
        if mode_online:
            try:
                results.append(score_online(case, use_daytona=args.daytona))
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "id": case.get("id"),
                        "ok": False,
                        "mode": "online",
                        "error": str(exc),
                        "use_daytona": args.daytona,
                        "tags": list(case.get("tags") or []),
                    }
                )
        else:
            row = score_offline(case)
            row["tags"] = list(case.get("tags") or [])
            results.append(row)

    from deepsupport_os.harness.eval_metrics import aggregate_summary

    summary = aggregate_summary(
        results,
        mode="online" if mode_online else "offline",
        use_daytona=bool(args.daytona) if mode_online else False,
    )
    out = ROOT / "data" / "benchmark" / "last_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persist cases + metrics into deepsupport.db
    run_id = None
    try:
        from deepsupport_os.db.eval_store import save_eval_run, sync_eval_cases

        synced = sync_eval_cases(path=args.cases)
        run_id = save_eval_run(summary, cases_path=str(args.cases))
        print(f"db: synced {synced['upserted']} cases, run_id={run_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"db persist skipped: {exc}")

    keys = (
        "total",
        "passed",
        "failed",
        "pass_rate",
        "mode",
        "use_daytona",
        "avg_elapsed_ms",
        "p50_elapsed_ms",
        "p95_elapsed_ms",
        "tool_hit_rate",
        "hitl_hit_rate",
        "offload_hit_rate",
        "skill_hit_rate",
        "subagent_hit_rate",
        "planning_hit_rate",
        "write_safety_rate",
        "grounding_rate",
        "long_task_pass_rate",
        "hitl_case_pass_rate",
        "interrupt_rate",
        "error_rate",
        "avg_tool_calls",
        "avg_step_count",
        "avg_subagent_dispatches",
    )
    payload = {k: summary.get(k) for k in keys}
    if summary.get("by_tag"):
        payload["by_tag"] = summary["by_tag"]
    if run_id:
        payload["run_id"] = run_id
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
