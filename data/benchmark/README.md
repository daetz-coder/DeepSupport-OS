# Benchmark 用例

| 文件 | 用途 |
|---|---|
| `mvp_cases.jsonl` | 30 条演示子集（快速冒烟） |
| `full_cases.jsonl` | **默认全面集（目标 150 条）**，覆盖 eval 指标维度 |
| `full_cases_coverage.json` | 生成时写出的覆盖统计 |

重新生成全面集：

```bash
cd backend
uv run python ../scripts/generate_full_cases.py
```

同步入库并离线跑分：

```bash
uv run python ../scripts/run_eval.py --offline --from-db
# 或指定路径
uv run python ../scripts/run_eval.py --offline --cases ../data/benchmark/full_cases.jsonl
```

## 指标覆盖（full_cases）

| 指标桶 | 用例设计 |
|---|---|
| `tool_hit_rate` | 按 Outlook/Teams/OneDrive/Office 等产品 + 工具族 |
| `hitl_hit_rate` / `interrupt_rate` | 密码重置、改许可、关单、升级；含 no-hitl 对照 |
| `write_safety_rate` | 强制走 HITL，禁止直接 `update_ticket` 终态 |
| `skill_hit_rate` | 每个 builtin skill ≥1 案 |
| `subagent_hit_rate` | knowledge / environment / ticket 单派 + 三合一 |
| `planning_hit_rate` / `long_task_pass_rate` | `planning` / `long-task` / `compound` |
| `grounding_rate` | `grounding` 标签 + 证据工具 |
| `offload_hit_rate` | `workspace_files` + `context-offload` |
| `by_tag` | 稳定 tag 枚举便于看板 |
| RAG（元数据） | `gold_doc_ids` / `gold_filenames`（当前只计 `search_docs` 调用；检索命中率待扩展 scorer） |
