# `harness/`

Deep Agents 运行时核心：把模型、工具、Skills、Subagents、Memory、Checkpoint、HITL 组装成可调用 Agent。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 包标记（无导出） |
| `agent.py` | 对外工厂：`build_model`、`get_checkpointer`（SQLite/MemorySaver）、`build_support_agent`、`purge_thread_checkpoint` |
| `builder.py` | `HarnessBuilder` + `RuntimePorts` + `INTERRUPT_ON`：真正调用 `create_deep_agent` |
| `prompts.py` | `SYSTEM_PROMPT` 硬约束；`build_system_prompt` 绑定 thread 工作区与 session memory 路径 |
| `subagents.py` | MVP 子代理定义：`knowledge-research` / `environment-diagnosis` / `ticket-operations` |
| `memory_files.py` | Memory 分层：`/memory/org.md` + `/memory/threads/{tid}/AGENTS.md`；ensure / 路径注入 |
| `workspace.py` | per-thread 工作区：`sanitize_thread_id`、`ensure_thread_workspace`、虚拟路径 |
| `daytona_backend.py` | `CompositeBackend`：workspace 可写、skills/org 只读、可选 Daytona `/sandbox/` |
| `hitl_runtime.py` | Resume 编排：解析 interrupt、apply / respond / reject、注入审批结果到转录 |
| `hitl_apply.py` | 批准后真实写库（密码重置、许可变更、关单/升级等） |
| `guard_middleware.py` | Agent 中间件：todos / ask_user 去重等运行时硬约束 |
| `capability_registry.py` | Tool / Skill / SubAgent 目录与启停过滤（构建时裁剪挂载） |
| `skills_registry.py` | 磁盘 Skills 扫描、导入、启停、`skill_source_paths` |
| `artifacts.py` | 规范产物名与 `manifest.json` 读写/校验 |
| `metrics.py` | 回合计时 `TurnTimer`、写 `metrics.json`、trace 摘要 |
| `run_overview.py` | 控制台用运行阶段分组与 overview 统计 |
| `state_extract.py` | 从 LangGraph state 提取 todos 等 |
| `runtime_context.py` | 请求级 ContextVar：`thread_id` / `task_id`（审计关联） |
| `tool_provenance.py` | 工具名 → local / knowledge / remote 来源标签 |
| `eval_metrics.py` | 评测指标目录与基于 trace 的打分/聚合 |
| `unit_of_work.py` | `WriteUnitOfWork`：Apply→Audit 同 span 语义 |
| `tracing.py` | OpenTelemetry span 辅助（无依赖时 no-op） |

## 组装顺序（简图）

```text
build_support_agent
  → HarnessBuilder.build
      → ensure_memory_files + workspace
      → backend (CompositeBackend)
      → tools + skills + subagents
      → interrupt_on + checkpointer
      → create_deep_agent(...)
```
