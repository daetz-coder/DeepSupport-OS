# 评测结果快照

> 生成时间：2026-08-05 09:46 UTC  
> 指标目录：[testing.md](./testing.md) · Baseline 说明：[baselines.md](./baselines.md)  
> 原始 JSON（gitignore）：`data/benchmark/last_eval.json`

## 环境

| 项 | 值 |
|---|---|
| 用例集 | `data/benchmark/full_cases.jsonl`（150） |
| Pytest | **61 passed** |
| Offline `run_id` | `0b46199c-1916-48d2-bb28-e0729bbc4f4c` |
| Online `run_id` | `3012f3c2-814e-4510-b4d2-96db644be1c0` |

## 用例覆盖（生成统计）

| 指标桶 | 用例数 |
|---|---:|
| tool_hit | 135 |
| hitl_hit | 15 |
| skill_hit | 17 |
| subagent_hit | 8 |
| planning_hit | 12 |
| grounding | 33 |
| offload | 5 |
| write_safety | 4 |
| long_task | 12 |
| rag_microsoft | 29 |

## Pytest

全量后端单测：**61 passed**（见 `data/benchmark/pytest_last.txt`）。

## Offline 评测

Schema / 门禁校验（不调用 LLM）：

| 指标 | 值 |
|---|---|
| `mode` | `offline` |
| `total` / `passed` / `failed` | 150 / 150 / 0 |
| `pass_rate` | **1.0** |
| `long_task_pass_rate` | 1.0 |
| `error_rate` | 0.0 |
| `run_id` | `0b46199c-1916-48d2-bb28-e0729bbc4f4c` |

## Online 评测（Full harness + LLM）

| 指标 | 含义 | 值 |
|---|---|---|
| `pass_rate` | 任务成功率 | 0.08 |
| `tool_hit_rate` | 工具命中率 | 0.875 |
| `hitl_hit_rate` | HITL 命中率 | 0.938 |
| `skill_hit_rate` | Skill 命中率 | 1 |
| `subagent_hit_rate` | SubAgent 命中率 | 0 |
| `planning_hit_rate` | 规划命中率 | 1 |
| `write_safety_rate` | 写安全率 | 1 |
| `grounding_rate` | 接地率 | — |
| `offload_hit_rate` | Offload 命中率 | 1 |
| `long_task_pass_rate` | 长任务通过率 | 0.167 |
| `hitl_case_pass_rate` | HITL 用例通过率 | 0.75 |
| `interrupt_rate` | 中断率 | 0.25 |
| `error_rate` | 异常率 | 0.893 |
| `avg_elapsed_ms` | 平均耗时 ms | 4249.9 |
| `p50_elapsed_ms` | P50 ms | 557.6 |
| `p95_elapsed_ms` | P95 ms | 30629.6 |
| `avg_tool_calls` | 平均工具调用 | 14.88 |
| `avg_step_count` | 平均步数 | 36.94 |
| `avg_subagent_dispatches` | 平均 SubAgent 委派 | 0.44 |

### 说明（余额中断）

本次 online 共 **150** 案，其中 **134** 案因 DeepSeek `Insufficient Balance` 失败（`error_rate=0.893`）。  
在余额耗尽前实际跑完（非余额错误）**16** 案，其中通过 **12**。  
下列命中率（`tool_hit_rate` 等）由 `aggregate_summary` 在**全部结果行**上统计；含大量提前失败案时，整体 `pass_rate` 会被拉低。充值后请重跑：

```bash
cd backend
uv run python ../scripts/run_eval.py --online --from-db
```

### Online 主要错误

| 次数 | 错误摘要 |
|---:|---|
| 134 | `Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': No` |

### Online `by_tag`

| tag | total | passed | pass_rate |
|---|---:|---:|---:|
| tool | 43 | 1 | 0.023 |
| grounding | 33 | 0 | 0 |
| rag | 29 | 0 | 0 |
| microsoft | 24 | 0 | 0 |
| ticket | 22 | 2 | 0.091 |
| excel | 21 | 2 | 0.095 |
| teams | 21 | 3 | 0.143 |
| office | 19 | 3 | 0.158 |
| outlook | 19 | 0 | 0 |
| onedrive | 17 | 0 | 0 |
| skill | 17 | 0 | 0 |
| short-task | 16 | 0 | 0 |
| hitl | 15 | 3 | 0.2 |
| account | 12 | 1 | 0.083 |
| long-task | 12 | 2 | 0.167 |
| microsoft365 | 12 | 0 | 0 |
| license | 11 | 2 | 0.182 |
| subagent | 9 | 1 | 0.111 |
| compound | 5 | 2 | 0.4 |
| context-offload | 5 | 0 | 0 |
| employee | 5 | 1 | 0.2 |
| escalation | 5 | 1 | 0.2 |
| offload | 5 | 0 | 0 |
| powerpoint | 5 | 0 | 0 |
| asset | 4 | 1 | 0.25 |
| case | 4 | 1 | 0.25 |
| harness | 4 | 0 | 0 |
| mfa | 4 | 0 | 0 |
| word | 4 | 0 | 0 |
| write-safety | 4 | 0 | 0 |
| no-hitl | 3 | 0 | 0 |
| notification | 3 | 0 | 0 |
| interrupt | 2 | 0 | 0 |
| planning | 2 | 0 | 0 |
| policy | 2 | 0 | 0 |
| report | 2 | 0 | 0 |
| checkpoint | 1 | 1 | 1 |
| smoke | 1 | 0 | 0 |
| write-safe-update | 1 | 0 | 0 |

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
