"""Analyze why online eval cases failed (from last_eval / partial)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "benchmark"


def main() -> None:
    candidates = [
        ROOT / "last_eval.resume_partial.json",
        ROOT / "last_eval.json",
    ]
    best = None
    best_score = -1
    for p in candidates:
        if not p.exists():
            continue
        s = json.loads(p.read_text(encoding="utf-8"))
        rs = s.get("results") or []
        done = [
            r
            for r in rs
            if "Insufficient Balance" not in str(r.get("error") or "")
        ]
        print(
            f"{p.name}: total={len(rs)} non_balance={len(done)} "
            f"passed={sum(1 for r in done if r.get('ok'))}"
        )
        if len(done) > best_score:
            best_score = len(done)
            best = (p, s)

    if not best:
        print("no eval results found")
        return

    path, summary = best
    rows = summary.get("results") or []
    print(f"\nUSING {path.name}")
    print(
        f"mode={summary.get('mode')} fast={summary.get('fast')} "
        f"pass_rate={summary.get('pass_rate')} "
        f"tool_hit={summary.get('tool_hit_rate')} "
        f"hitl_hit={summary.get('hitl_hit_rate')} "
        f"error_rate={summary.get('error_rate')}"
    )

    err_c: Counter[str] = Counter()
    gate_c: Counter[str] = Counter()
    tag_fail: Counter[str] = Counter()
    examples: dict[str, str] = {}
    missing_tools: Counter[str] = Counter()

    for r in rows:
        err = str(r.get("error") or "")
        cid = str(r.get("id") or "")
        if "Insufficient Balance" in err:
            err_c["API Insufficient Balance"] += 1
            continue
        if err.startswith("timeout"):
            err_c["timeout"] += 1
            examples.setdefault("timeout", cid)
            continue
        if "Recursion limit" in err:
            err_c["recursion_limit (agent loop)"] += 1
            examples.setdefault("recursion_limit", cid)
            continue
        if err:
            key = err.split("\n")[0][:120]
            err_c[key] += 1
            examples.setdefault(key[:50], cid)
            continue
        if r.get("ok"):
            continue
        bits = [
            k
            for k in (
                "tool_hit",
                "hitl_hit",
                "skill_hit",
                "subagent_hit",
                "planning_hit",
                "write_safety_hit",
                "grounding_hit",
                "offload_hit",
            )
            if r.get(k) is False
        ]
        label = "+".join(bits) or "ok=False_unknown"
        gate_c[label] += 1
        examples.setdefault(label, cid)
        for t in r.get("tags") or []:
            tag_fail[str(t)] += 1
        # which required tools missing?
        expect_tools = set()
        # reconstruct from tools_seen vs typical — use result fields if present
        seen = set(r.get("tools_seen") or [])
        # can't get expect from result; skip unless we load cases
        if r.get("tool_hit") is False:
            missing_tools[cid] += 1

    print("\n=== Exception / hard errors ===")
    for k, v in err_c.most_common(20):
        ex = examples.get(k) or examples.get(k[:50]) or ""
        print(f"{v:4d}  {k}" + (f"  e.g. {ex}" if ex else ""))

    print("\n=== Soft gate fails (ran but expectations missed) ===")
    for k, v in gate_c.most_common(20):
        print(f"{v:4d}  {k}  e.g. {examples.get(k, '')}")

    print("\n=== Tags among soft fails ===")
    for k, v in tag_fail.most_common(15):
        print(f"{v:4d}  {k}")

    finished = [
        r
        for r in rows
        if "Insufficient Balance" not in str(r.get("error") or "")
    ]
    ms = sorted(
        float(r["elapsed_ms"])
        for r in finished
        if isinstance(r.get("elapsed_ms"), (int, float))
    )
    if ms:
        print(
            f"\nTiming finished n={len(ms)} p50={ms[len(ms)//2]:.0f} "
            f"p95={ms[min(len(ms)-1, int(len(ms)*0.95))]:.0f} max={ms[-1]:.0f}"
        )
    print(
        f"Finished OK {sum(1 for r in finished if r.get('ok'))}/{len(finished)} "
        f"(excluding API-balance rows still pending)"
    )

    # Load expects to explain tool_hit fails
    cases_path = ROOT / "full_cases.jsonl"
    if cases_path.exists() and gate_c:
        by_id = {}
        for line in cases_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                by_id[c["id"]] = c
        miss: Counter[str] = Counter()
        for r in finished:
            if r.get("ok") or r.get("tool_hit") is not False:
                continue
            cid = r.get("id")
            case = by_id.get(cid) or {}
            need = set((case.get("expect") or {}).get("tools") or [])
            seen = set(r.get("tools_seen") or [])
            for t in sorted(need - seen):
                miss[t] += 1
        print("\n=== Missing required tools (among tool_hit fails) ===")
        for k, v in miss.most_common(15):
            print(f"{v:4d}  {k}")

        miss_sub: Counter[str] = Counter()
        for r in finished:
            if r.get("subagent_hit") is not False:
                continue
            cid = r.get("id")
            case = by_id.get(cid) or {}
            need = set((case.get("expect") or {}).get("subagents") or [])
            seen = set(r.get("subagents") or [])
            for t in sorted(need - seen):
                miss_sub[t] += 1
        if miss_sub:
            print("\n=== Missing subagents ===")
            for k, v in miss_sub.most_common():
                print(f"{v:4d}  {k}")


if __name__ == "__main__":
    main()
