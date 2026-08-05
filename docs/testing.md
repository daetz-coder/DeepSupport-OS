# 自动化测试与指标落库

DeepSupport OS 将 benchmark 用例与跑分结果写入同一 SQLite（`data/deepsupport.db`）。

## 表结构

| 表 | 用途 |
|---|---|
| `eval_cases` | 测试用例目录（默认自 `full_cases.jsonl` 同步；`mvp_cases.jsonl` 为演示子集） |
| `eval_runs` | 一次跑分汇总（核心列 + `summary_json` 扩展指标） |
| `eval_case_results` | 单案结果（核心列 + `result_json` 详情） |

## 指标目录

完整列表见 `GET /api/eval/metrics`（由 `harness/eval_metrics.py` 维护）。  
最新跑分快照见 [eval-results.md](./eval-results.md)。

### 成功 / 编排

| 指标 | 层级 | 含义 |
|---|---|---|
| `pass_rate` | run | 通过数 / 总数 |
| `tool_hit_rate` | run | required tools 命中率 |
| `skill_hit_rate` | run | expect.skills 被读取命中率 |
| `subagent_hit_rate` | run | expect.subagents 委派命中率 |
| `planning_hit_rate` | run | 长任务/复合题是否 `write_todos` |
| `long_task_pass_rate` | run | `long-task` 标签通过率 |
| `by_tag` | run | 按 tag 分组 pass_rate |

### 安全 / 接地

| 指标 | 层级 | 含义 |
|---|---|---|
| `hitl_hit_rate` | run | HITL 写工具期望命中率 |
| `hitl_case_pass_rate` | run | 含 hitl expect 的用例通过率 |
| `write_safety_rate` | run | 未用 `update_ticket` 直接关闭/升级 |
| `grounding_rate` | run | grounding 用例工具接地率 |
| `interrupt_rate` | run | 出现 pending_writes 的比例 |

### 产物 / 成本 / 时延

| 指标 | 层级 | 含义 |
|---|---|---|
| `offload_hit_rate` | run | 工作区/offload 期望命中率 |
| `avg_elapsed_ms` / `p50_elapsed_ms` / `p95_elapsed_ms` | run | 耗时分布 |
| `avg_tool_calls` / `avg_step_count` / `avg_subagent_dispatches` | run | 成本代理 |
| `error_rate` | run | 跑分异常比例 |

单案另有：`tool_hit`、`hitl_hit`、`offload_hit`、`skill_hit`、`subagent_hit`、`planning_hit`、`write_safety_hit`、`grounding_hit`、`elapsed_ms`、`tool_call_count`、`step_count` 等。

## 命令

```bash
cd backend

# 生成全面测试集（覆盖指标维度）
uv run python ../scripts/generate_full_cases.py

# 离线自动评测 + 写库（默认 full_cases.jsonl）
uv run python ../scripts/run_eval.py --offline --from-db

# 在线 LLM 评测（扩展指标主要在 online 有意义）
uv run python ../scripts/run_eval.py --online --limit 3

# 演示子集
uv run python ../scripts/run_eval.py --offline --cases ../data/benchmark/mvp_cases.jsonl

uv run pytest tests/test_eval_store.py tests/test_eval_metrics.py -q
```

用例说明见 [`data/benchmark/README.md`](../data/benchmark/README.md)。

## HTTP API

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/eval/metrics` | 指标目录 |
| GET | `/api/eval/cases` | 用例列表 |
| POST | `/api/eval/cases/sync` | 从 jsonl 同步用例 |
| POST | `/api/eval/run` | 离线跑分并写库 |
| GET | `/api/eval/runs` | 历史跑次 |
| GET | `/api/eval/runs/latest` | 最近一次（含 summary 扩展指标） |
| GET | `/api/eval/runs/{run_id}` | 跑次详情 |
