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
        }
    elapsed_ms = (time.perf_counter() - t0) * 1000
    msgs = result.get("messages", [])
    trace = build_trace(msgs)
    tool_names = {t.get("name") for t in trace.get("tool_calls") or []}
    expect = case.get("expect") or {}
    required_tools = set(expect.get("tools") or [])
    hitl_tools = set(expect.get("hitl") or [])
    pending = {p.get("name") for p in (trace.get("pending_writes") or [])}
    subagents = [s.get("subagent") for s in (trace.get("subagent_dispatches") or [])]

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

    ok = tool_hit and hitl_hit and offload_hit
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--offline", action="store_true", default=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--daytona",
        action="store_true",
        help="Attach Daytona as /sandbox/ sidecar (Skills stay local; default offline path is local-only)",
    )
    args = parser.parse_args()

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
                    }
                )
        else:
            results.append(score_offline(case))

    passed = sum(1 for r in results if r.get("ok"))
    elapsed = [r["elapsed_ms"] for r in results if isinstance(r.get("elapsed_ms"), (int, float))]
    hitl_ok = sum(1 for r in results if r.get("hitl_hit") is True)
    tool_ok = sum(1 for r in results if r.get("tool_hit") is True)
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "mode": "online" if mode_online else "offline",
        "use_daytona": bool(args.daytona) if mode_online else False,
        "avg_elapsed_ms": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
        "tool_hit_rate": round(tool_ok / len(results), 3) if mode_online and results else None,
        "hitl_hit_rate": round(hitl_ok / len(results), 3) if mode_online and results else None,
        "results": results,
    }
    out = ROOT / "data" / "benchmark" / "last_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    keys = (
        "total",
        "passed",
        "failed",
        "pass_rate",
        "mode",
        "use_daytona",
        "avg_elapsed_ms",
        "tool_hit_rate",
        "hitl_hit_rate",
    )
    print(json.dumps({k: summary[k] for k in keys}, ensure_ascii=False, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
