# Architecture

DeepSupport OS is an **enterprise IT support agent harness** built on Deep Agents.

## Layers

1. **UI / API** — Vue3 + FastAPI（tasks / SSE / HITL / meta Skills+MCP）
2. **Harness** — `create_deep_agent`：Skills、Subagents、Filesystem、Checkpoint、HITL、Todo
3. **Tools** — Local Tool Adapter（LangChain `@tool` → SQLite）+ optional Remote MCP
4. **Knowledge** — RAGLab HTTP + local `data/knowledge/*.md` fallback

```text
User → Vue → FastAPI /api/tasks[/stream|/resume]
              ↓
     Per-thread Deep Agents (prompt embeds /workspace/<tid>/)
     ├── Skills (/skills/…) · Memory (/memory/AGENTS.md)
     ├── Subagents (knowledge / environment / ticket)
     ├── Checkpoint (data/checkpoints.sqlite)
     └── HITL interrupt_on → hitl_apply → SQLite
              ↓
   Local tools + optional Remote MCP + RAGLabClient
              ↓
   workspace/{tid}/  {manifest,metrics,*.md}
```

## Module map

| Package | Role |
|---|---|
| `api/` | HTTP surface；`tasks.get_agent` 按 thread 缓存 |
| `harness/` | Agent factory、artifacts/manifest、metrics、HITL、Daytona |
| `mcp/` | Local tools + remote client + `servers/employee` FastMCP 模板 |
| `rag/` | RAGLab HTTP client |
| `db/` | Mock enterprise schema + task_store |
| `core/` | Settings、extensions、http_retry、auth |

## Thread lifecycle

1. Client 提交消息（可带 `thread_id`）→ `ensure_thread_workspace`
2. `get_agent(thread_id)` 构建/复用 agent（系统提示绑定该 tid 工作区）
3. `invoke` / `stream` → tools / skills / subagents / optional interrupt
4. `_build_record` 写 `manifest.json` + `metrics.json`，持久化 task_store
5. HITL：`resume` → `apply_approved_writes` → 再 invoke

## Dual-track tools（见 ADR）

详见 [adr/0001-mcp-dual-track.md](./adr/0001-mcp-dual-track.md)：本地 Adapter 与远程 MCP 并存；收敛路径已记录。

## Key packages

`deepsupport_os.harness.agent` · `deepsupport_os.mcp.tools` · `deepsupport_os.rag` · `deepsupport_os.db`
