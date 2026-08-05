# 评测结果快照

> 生成时间：2026-08-05 10:42 UTC  
> 指标目录：[testing.md](./testing.md) · Baseline 说明：[baselines.md](./baselines.md)  
> 数据源：`last_eval.resume_partial.json`（gitignore 目录 `data/benchmark/`）

## 环境

| 项 | 值 |
|---|---|
| 用例集 | `data/benchmark/full_cases.jsonl`（150） |
| Pytest | **61 passed** |
| Offline `run_id` | `0b46199c-1916-48d2-bb28-e0729bbc4f4c` |
| Online `run_id`（库内最近） | `3012f3c2-814e-4510-b4d2-96db644be1c0` |
| 快照说明 | 含 `--fast` 续跑；**推荐看「已跑完样本」** |

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

全量后端单测：**61 passed**。

## Offline 评测

| 指标 | 值 |
|---|---|
| `mode` | `offline` |
| `total` / `passed` / `failed` | 150 / 150 / 0 |
| `pass_rate` | **1.0** |
| `long_task_pass_rate` | 1.0 |
| `error_rate` | 0.0 |
| `run_id` | `0b46199c-1916-48d2-bb28-e0729bbc4f4c` |

## Online 评测（推荐：已跑完样本）

已实际跑完 **50** 案（排除仍为 `Insufficient Balance`、尚未续跑的 **100** 案）。通过 **30/50**。

| 指标 | 含义 | 值 |
|---|---|---|
| `total` / `passed` / `failed` | 规模 | 50 / 30 / 20 |
| `pass_rate` | 任务成功率 | 0.6 |
| `tool_hit_rate` | 工具命中率 | 0.895 |
| `hitl_hit_rate` | HITL 命中率 | 0.947 |
| `skill_hit_rate` | Skill 命中率 | 1 |
| `subagent_hit_rate` | SubAgent 命中率 | 0 |
| `planning_hit_rate` | 规划命中率 | 1 |
| `write_safety_rate` | 写安全率 | 1 |
| `grounding_rate` | 接地率 | 1 |
| `offload_hit_rate` | Offload 命中率 | 0.947 |
| `long_task_pass_rate` | 长任务通过率 | 0.286 |
| `hitl_case_pass_rate` | HITL 用例通过率 | 0.714 |
| `interrupt_rate` | 中断率 | 0.158 |
| `error_rate` | 异常率 | 0.24 |
| `avg_elapsed_ms` | 平均耗时 ms | 22450.8 |
| `p50_elapsed_ms` | P50 ms | 15845.6 |
| `p95_elapsed_ms` | P95 ms | 77002.3 |
| `avg_tool_calls` | 平均工具调用 | 9.68 |
| `avg_step_count` | 平均步数 | 24.29 |
| `avg_subagent_dispatches` | 平均 SubAgent 委派 | 0.24 |

### 解读（已跑完）

- **强项**：`tool_hit≈0.895`、`hitl_hit≈0.947`、`planning/write_safety/grounding` 高。
- **短板**：`subagent_hit=0`；`long_task_pass_rate=0.286`；`error_rate=0.24`（多为 Agent 递归上限）。
- **`--fast` 注意**：关闭 skills Glob / RAGLab HTTP，`skill_hit` 偏乐观；与生产全量 harness 不完全等价。

### 已跑完样本：主要硬错误

| 次数 | 错误摘要 |
|---:|---|
| 11 | `Recursion limit (agent loop)` |
| 1 | `timeout` |

### 已跑完样本：`by_tag`

| tag | total | passed | pass_rate |
|---|---:|---:|---:|
| ticket | 12 | 5 | 0.417 |
| hitl | 10 | 5 | 0.5 |
| short-task | 10 | 8 | 0.8 |
| license | 8 | 6 | 0.75 |
| long-task | 7 | 2 | 0.286 |
| outlook | 6 | 1 | 0.167 |
| skill | 6 | 1 | 0.167 |
| account | 5 | 5 | 1 |
| grounding | 5 | 4 | 0.8 |
| teams | 5 | 3 | 0.6 |
| tool | 5 | 5 | 1 |
| case | 4 | 2 | 0.5 |
| compound | 4 | 2 | 0.5 |
| employee | 4 | 4 | 1 |
| excel | 4 | 2 | 0.5 |
| office | 4 | 3 | 0.75 |
| onedrive | 4 | 1 | 0.25 |
| asset | 3 | 3 | 1 |
| context-offload | 3 | 0 | 0 |
| escalation | 3 | 1 | 0.333 |
| offload | 3 | 0 | 0 |
| harness | 2 | 0 | 0 |
| mfa | 2 | 1 | 0.5 |
| no-hitl | 2 | 2 | 1 |
| notification | 2 | 1 | 0.5 |
| rag | 2 | 1 | 0.5 |
| subagent | 2 | 1 | 0.5 |
| write-safety | 2 | 0 | 0 |
| checkpoint | 1 | 1 | 1 |
| interrupt | 1 | 1 | 1 |
| planning | 1 | 0 | 0 |
| policy | 1 | 1 | 1 |
| powerpoint | 1 | 0 | 0 |

## Online 全量 150（含未续跑余额失败，仅供对照）

| 指标 | 含义 | 值 |
|---|---|---|
| `total` / `passed` / `failed` | 规模 | 150 / 30 / 120 |
| `pass_rate` | 任务成功率 | 0.2 |
| `tool_hit_rate` | 工具命中率 | 0.895 |
| `hitl_hit_rate` | HITL 命中率 | 0.947 |
| `skill_hit_rate` | Skill 命中率 | 1 |
| `subagent_hit_rate` | SubAgent 命中率 | 0 |
| `planning_hit_rate` | 规划命中率 | 1 |
| `write_safety_rate` | 写安全率 | 1 |
| `grounding_rate` | 接地率 | 1 |
| `offload_hit_rate` | Offload 命中率 | 0.947 |
| `long_task_pass_rate` | 长任务通过率 | 0.167 |
| `hitl_case_pass_rate` | HITL 用例通过率 | 0.714 |
| `interrupt_rate` | 中断率 | 0.158 |
| `error_rate` | 异常率 | 0.747 |
| `avg_elapsed_ms` | 平均耗时 ms | 7883.9 |
| `p50_elapsed_ms` | P50 ms | 602.1 |
| `p95_elapsed_ms` | P95 ms | 44494.4 |
| `avg_tool_calls` | 平均工具调用 | 9.68 |
| `avg_step_count` | 平均步数 | 24.29 |
| `avg_subagent_dispatches` | 平均 SubAgent 委派 | 0.24 |

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
