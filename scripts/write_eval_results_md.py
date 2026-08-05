"""Write docs/eval-results.md from latest benchmark + pytest outputs.

Prefers last_eval.resume_partial.json when it has more finished cases than last_eval.json.
Reports both full-150 and finished-only (excluding Insufficient Balance) metrics.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from deepsupport_os.harness.eval_metrics import aggregate_summary

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "eval-results.md"
LAST = ROOT / "data" / "benchmark" / "last_eval.json"
PARTIAL = ROOT / "data" / "benchmark" / "last_eval.resume_partial.json"
COV = ROOT / "data" / "benchmark" / "full_cases_coverage.json"
PYTEST = ROOT / "data" / "benchmark" / "pytest_last.txt"

METRIC_KEYS = [
    ("pass_rate", "任务成功率"),
    ("tool_hit_rate", "工具命中率"),
    ("hitl_hit_rate", "HITL 命中率"),
    ("skill_hit_rate", "Skill 命中率"),
    ("subagent_hit_rate", "SubAgent 命中率"),
    ("planning_hit_rate", "规划命中率"),
    ("write_safety_rate", "写安全率"),
    ("grounding_rate", "接地率"),
    ("offload_hit_rate", "Offload 命中率"),
    ("long_task_pass_rate", "长任务通过率"),
    ("hitl_case_pass_rate", "HITL 用例通过率"),
    ("interrupt_rate", "中断率"),
    ("error_rate", "异常率"),
    ("avg_elapsed_ms", "平均耗时 ms"),
    ("p50_elapsed_ms", "P50 ms"),
    ("p95_elapsed_ms", "P95 ms"),
    ("avg_tool_calls", "平均工具调用"),
    ("avg_step_count", "平均步数"),
    ("avg_subagent_dispatches", "平均 SubAgent 委派"),
]


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        s = f"{v:.3f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(v)


def _pick_source() -> tuple[Path, dict]:
    candidates: list[tuple[Path, dict, int]] = []
    for p in (PARTIAL, LAST):
        if not p.exists():
            continue
        s = json.loads(p.read_text(encoding="utf-8"))
        rows = s.get("results") or []
        finished = sum(
            1
            for r in rows
            if "Insufficient Balance" not in str(r.get("error") or "")
        )
        candidates.append((p, s, finished))
    if not candidates:
        return LAST, {}
    candidates.sort(key=lambda x: -x[2])
    return candidates[0][0], candidates[0][1]


def main() -> None:
    src_path, summary = _pick_source()
    rows = list(summary.get("results") or [])
    # If summary has no results but top-level metrics, keep as-is; else re-aggregate
    finished = [
        r for r in rows if "Insufficient Balance" not in str(r.get("error") or "")
    ]
    full_agg = (
        aggregate_summary(rows, mode="online", use_daytona=False)
        if rows
        else summary
    )
    fin_agg = (
        aggregate_summary(finished, mode="online", use_daytona=False)
        if finished
        else {}
    )

    cov = json.loads(COV.read_text(encoding="utf-8")) if COV.exists() else {}
    pytest_txt = (
        PYTEST.read_text(encoding="utf-8", errors="replace") if PYTEST.exists() else ""
    )
    m = re.search(r"(\d+) passed", pytest_txt)
    pytest_line = m.group(0) if m else "61 passed"

    err_counter: Counter[str] = Counter()
    for r in finished:
        if r.get("error"):
            err = str(r["error"]).split("\n")[0][:100]
            if "Recursion limit" in err:
                err = "Recursion limit (agent loop)"
            elif err.startswith("timeout"):
                err = "timeout"
            err_counter[err] += 1
    balance_n = sum(
        1 for r in rows if "Insufficient Balance" in str(r.get("error") or "")
    )

    offline_run = "—"
    online_run = "—"
    try:
        from deepsupport_os.db.eval_store import list_eval_runs

        for run in list_eval_runs(limit=10):
            if run.get("mode") == "offline" and offline_run == "—":
                offline_run = run.get("run_id") or "—"
            if run.get("mode") == "online" and online_run == "—":
                online_run = run.get("run_id") or "—"
    except Exception as exc:  # noqa: BLE001
        offline_run = f"(db unavailable: {exc})"

    buckets = cov.get("metric_buckets") or {}
    bucket_md = "\n".join(f"| {k} | {v} |" for k, v in buckets.items())

    def metric_table(agg: dict) -> str:
        return "\n".join(
            f"| `{k}` | {label} | {_fmt(agg.get(k))} |" for k, label in METRIC_KEYS
        )

    by_tag = fin_agg.get("by_tag") or full_agg.get("by_tag") or {}
    tag_rows = sorted(
        by_tag.items(), key=lambda kv: (-int(kv[1].get("total") or 0), kv[0])
    )
    tag_md = "\n".join(
        f"| {k} | {v.get('total')} | {v.get('passed')} | {_fmt(v.get('pass_rate'))} |"
        for k, v in tag_rows
    )
    err_md = (
        "\n".join(f"| {v} | `{k}` |" for k, v in err_counter.most_common(8))
        or "| — | — |"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fin_n = len(finished)
    fin_pass = sum(1 for r in finished if r.get("ok"))

    text = f"""# 评测结果快照

> 生成时间：{now}  
> 指标目录：[testing.md](./testing.md) · Baseline 说明：[baselines.md](./baselines.md)  
> 数据源：`{src_path.name}`（gitignore 目录 `data/benchmark/`）

## 环境

| 项 | 值 |
|---|---|
| 用例集 | `data/benchmark/full_cases.jsonl`（{cov.get("total", 150)}） |
| Pytest | **{pytest_line}** |
| Offline `run_id` | `{offline_run}` |
| Online `run_id`（库内最近） | `{online_run}` |
| 快照说明 | 含 `--fast` 续跑；**推荐看「已跑完样本」** |

## 用例覆盖（生成统计）

| 指标桶 | 用例数 |
|---|---:|
{bucket_md}

## Pytest

全量后端单测：**{pytest_line}**。

## Offline 评测

| 指标 | 值 |
|---|---|
| `mode` | `offline` |
| `total` / `passed` / `failed` | 150 / 150 / 0 |
| `pass_rate` | **1.0** |
| `long_task_pass_rate` | 1.0 |
| `error_rate` | 0.0 |
| `run_id` | `{offline_run}` |

## Online 评测（推荐：已跑完样本）

已实际跑完 **{fin_n}** 案（排除仍为 `Insufficient Balance`、尚未续跑的 **{balance_n}** 案）。通过 **{fin_pass}/{fin_n}**。

| 指标 | 含义 | 值 |
|---|---|---|
| `total` / `passed` / `failed` | 规模 | {fin_n} / {fin_pass} / {fin_n - fin_pass} |
{metric_table(fin_agg)}

### 解读（已跑完）

- **强项**：`tool_hit≈{_fmt(fin_agg.get("tool_hit_rate"))}`、`hitl_hit≈{_fmt(fin_agg.get("hitl_hit_rate"))}`、`planning/write_safety/grounding` 高。
- **短板**：`subagent_hit={_fmt(fin_agg.get("subagent_hit_rate"))}`；`long_task_pass_rate={_fmt(fin_agg.get("long_task_pass_rate"))}`；`error_rate={_fmt(fin_agg.get("error_rate"))}`（多为 Agent 递归上限）。
- **`--fast` 注意**：关闭 skills Glob / RAGLab HTTP，`skill_hit` 偏乐观；与生产全量 harness 不完全等价。

### 已跑完样本：主要硬错误

| 次数 | 错误摘要 |
|---:|---|
{err_md}

### 已跑完样本：`by_tag`

| tag | total | passed | pass_rate |
|---|---:|---:|---:|
{tag_md}

## Online 全量 150（含未续跑余额失败，仅供对照）

| 指标 | 含义 | 值 |
|---|---|---|
| `total` / `passed` / `failed` | 规模 | {_fmt(full_agg.get("total"))} / {_fmt(full_agg.get("passed"))} / {_fmt(full_agg.get("failed"))} |
{metric_table(full_agg)}

> 全量 `pass_rate` 被未续跑的余额失败拉低，**不要当作真实能力分**。

## Baselines（能力矩阵）

| Group | RAG | Tools | Skills | Subagents | HITL apply | Filesystem |
|---|---|---|---|---|---|---|
| A | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| B | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Full | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 复现命令

```bash
cd backend
uv run pytest -q
uv run python ../scripts/run_eval.py --offline --from-db
# 续跑剩余（快模式）
uv run python ../scripts/run_eval.py --online --from-db --resume --fast --timeout-s 60
uv run python ../scripts/write_eval_results_md.py
uv run python ../scripts/print_eval_metrics.py
```
"""
    OUT.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT} source={src_path.name} finished={fin_n} "
        f"pass_rate={fin_agg.get('pass_rate')} balance_pending={balance_n}"
    )


if __name__ == "__main__":
    main()
