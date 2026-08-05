# Architecture

DeepSupport OS is an **enterprise IT support agent harness** built on Deep Agents.

> 配套：系统架构图 `docs/architecture/deepsupport-os-architecture.svg`；案例图 `docs/architecture/case-*.svg`（Outlook+HITL / ask_user 多轮 / 在线评测 / Docker 拓扑，本地交付物）。

## Layers

1. **UI / API** — Vue3 + FastAPI（`/api/tasks` SSE+resume、`/api/meta` Skills+MCP、`/api/eval`、`/health`、`/admin/seed`）
2. **Harness** — `create_deep_agent`：Skills、Subagents、Filesystem、Checkpoint、HITL（`interrupt_on` + `when` 守卫）、Todo
3. **Tools** — Local Tool Adapter（LangChain `@tool` → SQLite）+ 可选 Remote MCP；工具带来源标签（`tool_provenance`）
4. **Knowledge** — RAGLab HTTP（`RAGLAB_KB=deepsupport`）+ 本地 `data/knowledge/*.md` fallback
5. **Eval** — 离线/在线跑分：`scripts/run_eval.py` + `/api/eval` + SQLite 落库

```text
User → Vue → FastAPI /api/tasks[/stream|/resume]
              ↓
     Per-thread Deep Agents (prompt embeds /workspace/<tid>/)
     ├── Skills (/skills/…) · Memory (/memory/org.md + /memory/AGENTS.md)
     ├── Subagents (knowledge / environment / ticket)
     ├── Checkpoint (data/checkpoints.sqlite)
     └── HITL interrupt_on → hitl_apply → SQLite
              ↓
   Local tools + optional Remote MCP + RAGLabClient
              ↓
   workspace/{tid}/  {manifest,metrics,*.md}
              ↓
   Eval: run_eval → eval_runs / eval_case_results
```

## Module map

| Package | Role |
|---|---|
| `api/` | HTTP surface；`tasks.get_agent` 按 thread 缓存；`eval` 离线跑分 |
| `harness/` | Agent factory（builder）、artifacts/manifest、metrics、HITL、Daytona、run_overview、eval_metrics |
| `mcp/` | Local tools + remote client + `servers/employee` FastMCP 模板 |
| `rag/` | RAGLab HTTP client（KB-aware） |
| `db/` | Mock enterprise schema + task_store + eval_store（eval_cases/runs/results） |
| `core/` | Settings、extensions、auth（`require_admin`）、http_retry |

## Thread lifecycle

1. Client 提交消息（可带 `thread_id`）→ `ensure_thread_workspace`
2. `get_agent(thread_id)` 构建/复用 agent（系统提示绑定该 tid 工作区，`_agents` 字典缓存、上限 48）
3. `invoke` / `stream` → tools / skills / subagents / optional interrupt
4. `_build_record` 写 `manifest.json` + `metrics.json`，持久化 task_store
5. HITL：`resume` → `_prepare_resume`（按中断的 `action_requests` 精确取 pending）→ `apply_approved_writes` → 审批结果注入 checkpoint 转录 → 再 invoke
6. `ask_user`：agent 缺上下文时中断提问 → 用户回答 → `resume`（answer 作为 `Command(resume=…)`）→ 继续

## 鉴权

默认监听 `127.0.0.1`（Docker 用 `API_HOST=0.0.0.0`）。设置 `ADMIN_TOKEN` 后，所有**变更型**端点需 `X-Admin-Token` 头（`api/auth.py::require_admin`）：

- `/api/meta/*` 的 POST/PATCH/DELETE（Skills 启停/导入、MCP 配置）
- `/admin/seed`、`/api/eval/run`、`/api/eval/cases/sync`

前端在 `VITE_ADMIN_TOKEN` 配置时自动带上该头（`api/client.ts::apiHeaders`）。

## Memory 分层

- `/memory/org.md` — 稳定组织事实，**入库**（`memory/org.md`）
- `/memory/AGENTS.md` — 会话运行时记忆（agent 逐轮追加），**gitignore**、启动时自动重建（`harness/memory_files.py`）

## Eval（评测）

- 离线：`POST /api/eval/run` 或 `scripts/run_eval.py --offline`（校验用例 schema，不调 LLM）
- 在线：`scripts/run_eval.py --online`（逐 case 跑 agent → trace 打分 → 汇总）
- 指标目录：`GET /api/eval/metrics`（`harness/eval_metrics.py`）；落库表 `eval_cases` / `eval_runs` / `eval_case_results`
- 在线评测用内存 checkpoint（`MemorySaver`）且评分后清理工作区，避免累积
- 详见 [docs/testing.md](./testing.md) · 基线设计 [docs/baselines.md](./baselines.md)

## Dual-track tools（见 ADR）

详见 [adr/0001-mcp-dual-track.md](./adr/0001-mcp-dual-track.md)：本地 Adapter 与远程 MCP 并存；收敛路径已记录。

## Key packages

`deepsupport_os.harness.agent` · `deepsupport_os.mcp.tools` · `deepsupport_os.rag` · `deepsupport_os.db` · `deepsupport_os.harness.eval_metrics`
