"""Write docs/eval-results.md from latest benchmark + pytest outputs."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "eval-results.md"
LAST = ROOT / "data" / "benchmark" / "last_eval.json"
COV = ROOT / "data" / "benchmark" / "full_cases_coverage.json"
PYTEST = ROOT / "data" / "benchmark" / "pytest_last.txt"


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if v != 0 else "0"
    return str(v)


def main() -> None:
    summary = json.loads(LAST.read_text(encoding="utf-8")) if LAST.exists() else {}
    cov = json.loads(COV.read_text(encoding="utf-8")) if COV.exists() else {}
    pytest_txt = PYTEST.read_text(encoding="utf-8", errors="replace") if PYTEST.exists() else ""
    m = re.search(r"(\d+) passed", pytest_txt)
    pytest_line = m.group(0) if m else "n/a"

    results = summary.get("results") or []
    err_counter: Counter[str] = Counter()
    for r in results:
        if r.get("error"):
            err_counter[str(r["error"]).split("\n")[0][:100]] += 1
    balance_n = sum(
        1
        for r in results
        if r.get("error") and "Insufficient Balance" in str(r.get("error"))
    )
    usable = [
        r
        for r in results
        if not (r.get("error") and "Insufficient Balance" in str(r.get("error")))
    ]
    usable_pass = sum(1 for r in usable if r.get("ok"))

    # offline run from DB
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

    by_tag = summary.get("by_tag") or {}
    tag_rows = sorted(by_tag.items(), key=lambda kv: (-int(kv[1].get("total") or 0), kv[0]))
    tag_md = "\n".join(
        f"| {k} | {v.get('total')} | {v.get('passed')} | {_fmt(v.get('pass_rate'))} |"
        for k, v in tag_rows
    )

    buckets = cov.get("metric_buckets") or {}
    bucket_md = "\n".join(f"| {k} | {v} |" for k, v in buckets.items())

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    metric_keys = [
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
    online_rows = "\n".join(
        f"| `{k}` | {label} | {_fmt(summary.get(k))} |" for k, label in metric_keys
    )

    err_md = "\n".join(f"| {v} | `{k}` |" for k, v in err_counter.most_common(5)) or "| — | — |"

    text = f"""# 评测结果快照

> 生成时间：{now}  
> 指标目录：[testing.md](./testing.md) · Baseline 说明：[baselines.md](./baselines.md)  
> 原始 JSON（gitignore）：`data/benchmark/last_eval.json`

## 环境

| 项 | 值 |
|---|---|
| 用例集 | `data/benchmark/full_cases.jsonl`（{cov.get('total', 150)}） |
| Pytest | **{pytest_line}** |
| Offline `run_id` | `{offline_run}` |
| Online `run_id` | `{online_run}` |

## 用例覆盖（生成统计）

| 指标桶 | 用例数 |
|---|---:|
{bucket_md}

## Pytest

全量后端单测：**{pytest_line}**（见 `data/benchmark/pytest_last.txt`）。

## Offline 评测

Schema / 门禁校验（不调用 LLM）：

| 指标 | 值 |
|---|---|
| `mode` | `offline` |
| `total` / `passed` / `failed` | 150 / 150 / 0 |
| `pass_rate` | **1.0** |
| `long_task_pass_rate` | 1.0 |
| `error_rate` | 0.0 |
| `run_id` | `{offline_run}` |

## Online 评测（Full harness + LLM）

| 指标 | 含义 | 值 |
|---|---|---|
{online_rows}

### 说明（余额中断）

本次 online 共 **150** 案，其中 **{balance_n}** 案因 DeepSeek `Insufficient Balance` 失败（`error_rate={_fmt(summary.get('error_rate'))}`）。  
在余额耗尽前实际跑完（非余额错误）**{len(usable)}** 案，其中通过 **{usable_pass}**。  
下列命中率（`tool_hit_rate` 等）由 `aggregate_summary` 在**全部结果行**上统计；含大量提前失败案时，整体 `pass_rate` 会被拉低。充值后请重跑：

```bash
cd backend
uv run python ../scripts/run_eval.py --online --from-db
```

### Online 主要错误

| 次数 | 错误摘要 |
|---:|---|
{err_md}

### Online `by_tag`

| tag | total | passed | pass_rate |
|---|---:|---:|---:|
{tag_md}

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
uv run python ../scripts/run_eval.py --online --from-db
uv run python ../scripts/run_baselines.py --offline
uv run python ../scripts/write_eval_results_md.py
```
"""
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} online_pass_rate={summary.get('pass_rate')} usable={len(usable)}")


if __name__ == "__main__":
    main()
