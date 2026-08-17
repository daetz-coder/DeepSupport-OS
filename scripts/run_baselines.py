"""Minimal Baseline A / B runners for harness comparison.

Baseline A — RAG only (search_docs), no write tools / skills / subagents.
Baseline B — LLM + MCP tools via create_agent, no Skills / Subagents / Daytona FS.

Usage:
  cd backend
  uv run python ../scripts/run_baselines.py --offline
  uv run python ../scripts/run_baselines.py --online --limit 3 --profile A
  uv run python ../scripts/run_baselines.py --online --limit 3 --profile B
  uv run python ../scripts/run_baselines.py --online --limit 3 --profile both
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "benchmark" / "mvp_cases.jsonl"
OUT = ROOT / "data" / "benchmark" / "last_baselines.json"


def load_cases(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    if limit:
        rows = rows[:limit]
    return rows


def score_expect(case: dict[str, Any], tool_names: set[str], pending: set[str]) -> dict[str, Any]:
    expect = case.get("expect") or {}
    required_tools = set(expect.get("tools") or [])
    hitl_tools = set(expect.get("hitl") or [])
    tool_hit = required_tools.issubset(tool_names) if required_tools else True
    # Baseline A cannot satisfy HITL writes by design
    hitl_hit = hitl_tools.issubset(tool_names | pending) if hitl_tools else True
    return {
        "tool_hit": tool_hit,
        "hitl_hit": hitl_hit,
        "ok": tool_hit and hitl_hit,
        "required_tools": sorted(required_tools),
        "required_hitl": sorted(hitl_tools),
    }


def run_baseline_a(case: dict[str, Any]) -> dict[str, Any]:
    """RAG-only: call search_docs, no agent loop / writes."""
    from deepsupport_os.rag.knowledge_tools import search_docs

    t0 = time.perf_counter()
    result = search_docs.invoke({"query": case["question"], "top_k": 3})
    elapsed_ms = (time.perf_counter() - t0) * 1000
    tools_seen = {"search_docs"} if result.get("ok") else set()
    scored = score_expect(case, tools_seen, set())
    return {
        "id": case.get("id"),
        "profile": "A",
        "mode": "online",
        "elapsed_ms": round(elapsed_ms, 1),
        "tools_seen": sorted(tools_seen),
        "pending_writes": [],
        "backend": result.get("backend"),
        "can_write": False,
        "notes": "RAG-only; cannot perform HITL writes or account mutations",
        **scored,
    }


def run_baseline_b(case: dict[str, Any]) -> dict[str, Any]:
    """Tool-calling agent without Skills / Subagents / Deep Agents backend."""
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import MemorySaver

    from deepsupport_os.api.trace import build_trace
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.db import init_db
    from deepsupport_os.db.seed import seed_database
    from deepsupport_os.harness.agent import build_model
    from deepsupport_os.mcp.tools import main_agent_tools
    from deepsupport_os.rag.knowledge_tools import KNOWLEDGE_TOOLS

    settings = get_settings()
    if not settings.llm_configured:
        return {"id": case.get("id"), "profile": "B", "ok": False, "error": "llm_not_configured"}

    init_db()
    seed_database(force=False)
    tools = list(main_agent_tools()) + list(KNOWLEDGE_TOOLS)
    agent = create_agent(
        model=build_model(),
        tools=tools,
        system_prompt=(
            "你是简易 IT 支持助手。可用工具查询账号与文档；"
            "高风险写操作可调用但无 Skills/Subagents 规划。"
        ),
        checkpointer=MemorySaver(),
        name="baseline-b",
    )
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    t0 = time.perf_counter()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": case["question"]}]},
        config=config,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    msgs = result.get("messages", [])
    trace = build_trace(msgs)
    tool_names = {t.get("name") for t in (trace.get("tool_calls") or []) if t.get("name")}
    pending = {p.get("name") for p in (trace.get("pending_writes") or []) if p.get("name")}
    scored = score_expect(case, tool_names, pending)
    return {
        "id": case.get("id"),
        "profile": "B",
        "mode": "online",
        "elapsed_ms": round(elapsed_ms, 1),
        "tools_seen": sorted(tool_names),
        "pending_writes": sorted(pending),
        "can_write": True,
        "notes": "No Skills/Subagents/Daytona filesystem",
        **scored,
    }


def offline_capability_matrix() -> dict[str, Any]:
    return {
        "A": {
            "rag": True,
            "tools": False,
            "skills": False,
            "subagents": False,
            "hitl_apply": False,
            "filesystem": False,
        },
        "B": {
            "rag": True,
            "tools": True,
            "skills": False,
            "subagents": False,
            "hitl_apply": False,
            "filesystem": False,
        },
        "Full": {
            "rag": True,
            "tools": True,
            "skills": True,
            "subagents": True,
            "hitl_apply": True,
            "filesystem": True,
        },
    }


def summarize(results: list[dict[str, Any]], profile: str) -> dict[str, Any]:
    rows = [r for r in results if r.get("profile") == profile]
    if not rows:
        return {"profile": profile, "total": 0}
    passed = sum(1 for r in rows if r.get("ok"))
    elapsed = [r["elapsed_ms"] for r in rows if isinstance(r.get("elapsed_ms"), (int, float))]
    return {
        "profile": profile,
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "avg_elapsed_ms": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--profile", choices=["A", "B", "both"], default="both")
    args = parser.parse_args()

    if not args.online and not args.offline:
        args.offline = True

    cases = load_cases(args.cases, args.limit)
    results: list[dict[str, Any]] = []

    if args.offline:
        report = {
            "mode": "offline",
            "capability_matrix": offline_capability_matrix(),
            "note": "Offline documents expected capability gaps; run --online for live scores.",
            "cases_available": len(load_cases(args.cases)),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["capability_matrix"], ensure_ascii=False, indent=2))
        print(f"wrote {OUT}")
        return

    profiles = ["A", "B"] if args.profile == "both" else [args.profile]
    for case in cases:
        if "A" in profiles:
            try:
                results.append(run_baseline_a(case))
            except Exception as exc:  # noqa: BLE001
                results.append({"id": case.get("id"), "profile": "A", "ok": False, "error": str(exc)})
        if "B" in profiles:
            try:
                results.append(run_baseline_b(case))
            except Exception as exc:  # noqa: BLE001
                results.append({"id": case.get("id"), "profile": "B", "ok": False, "error": str(exc)})

    summary = {
        "mode": "online",
        "capability_matrix": offline_capability_matrix(),
        "summaries": [summarize(results, p) for p in profiles],
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summaries": summary["summaries"]}, ensure_ascii=False, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
