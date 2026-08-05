"""Print current eval metrics from resume partial / last_eval."""

from __future__ import annotations

import json
from pathlib import Path

from deepsupport_os.harness.eval_metrics import aggregate_summary

ROOT = Path(__file__).resolve().parents[1] / "data" / "benchmark"
KEYS = [
    "total",
    "passed",
    "failed",
    "pass_rate",
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
    "avg_elapsed_ms",
    "p50_elapsed_ms",
    "p95_elapsed_ms",
    "avg_tool_calls",
    "avg_step_count",
    "avg_subagent_dispatches",
]


def show(title: str, rows: list) -> dict:
    s = aggregate_summary(rows, mode="online", use_daytona=False)
    print(title)
    for k in KEYS:
        print(f"  {k}: {s.get(k)}")
    return s


def main() -> None:
    partial = json.loads((ROOT / "last_eval.resume_partial.json").read_text(encoding="utf-8"))
    rows = partial.get("results") or []
    finished = [
        r for r in rows if "Insufficient Balance" not in str(r.get("error") or "")
    ]
    show("=== A) 全量 150（含未续跑余额失败）===", rows)
    s = show("=== B) 已跑完样本（推荐看这个）===", finished)
    print("=== by_tag（已跑完）===")
    bt = s.get("by_tag") or {}
    for tag, v in sorted(bt.items(), key=lambda kv: (-kv[1].get("total", 0), kv[0]))[:20]:
        print(f"  {tag}: {v.get('passed')}/{v.get('total')} = {v.get('pass_rate')}")


if __name__ == "__main__":
    main()
