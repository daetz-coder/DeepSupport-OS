# API Overview

Base URL: `http://127.0.0.1:8000`（默认绑定 loopback；Docker 为 `0.0.0.0`）

OpenAPI：[/docs](http://127.0.0.1:8000/docs)

## System

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info + `llm_configured` |
| GET | `/health` | **Liveness only**（compose healthcheck 用） |
| GET | `/api/health/deps` | RAGLab + Daytona Sandbox 探测 |
| POST | `/admin/seed?force=` | Reseed mock DB（可选 `X-Admin-Token`） |

## Tasks

| Method | Path | Description |
|---|---|---|
| GET | `/api/tasks` | List recent tasks (runs) |
| GET | `/api/tasks/threads` | List conversations (thread → nested runs) |
| DELETE | `/api/tasks/threads/{thread_id}` | 清除会话（删除该 Thread 全部 runs + 工作区） |
| POST | `/api/tasks` | Sync harness turn（可传 `thread_id` 续聊） |
| POST | `/api/tasks/stream` | SSE turn（含 `token`） |
| POST | `/api/tasks/resume` | 同步续跑：`interrupt_type=ask` + `answer`，或 HITL `approved` |
| POST | `/api/tasks/resume/stream` | SSE 续跑（与 `/stream` 相同事件：`token` / `interrupt` / `done`） |
| GET | `/api/tasks/{task_id}` | Task snapshot（含 `trace` / `overview` / `manifest` / `metrics`） |
| GET | `/api/tasks/{task_id}/trace` | Structured execution trace |
| GET | `/api/tasks/{task_id}/artifacts` | Workspace file list |
| GET | `/api/tasks/{task_id}/artifacts/{path}` | Artifact content |
| GET | `/api/tasks/meta/audit` | Recent tool audit log |

### SSE events (`POST /api/tasks/stream` · `POST /api/tasks/resume/stream`)

`status` · `token` · `tool_start` · `tool_end` · `subagent` · `context_offload` · `message` · `todos` · `interrupt` · `error` · `done`

`done` payload includes `manifest`（`workspace/{tid}/manifest.json`）与 `metrics`（`metrics.json`）。

## Meta — Skills

| Method | Path | Auth |
|---|---|---|
| GET | `/api/meta/skills` | — |
| POST | `/api/meta/skills/{name}/toggle` | `X-Admin-Token` if `ADMIN_TOKEN` set |
| POST | `/api/meta/skills/import` | same |
| PATCH | `/api/meta/skills/settings` | same |

## Meta — MCP

| Method | Path | Auth |
|---|---|---|
| GET | `/api/meta/mcp` | — |
| PATCH | `/api/meta/mcp/settings` | admin token if set |
| POST | `/api/meta/mcp/servers` | admin token if set |
| POST | `/api/meta/mcp/servers/{name}/toggle` | admin token if set |
| DELETE | `/api/meta/mcp/servers/{name}` | admin token if set |
| POST | `/api/meta/mcp/reload` | admin token if set |

## Workspace side files

每线程目录 `workspace/{thread_id}/`：

- `manifest.json` — 产物清单 + canonical 校验
- `metrics.json` — 本回合 step/tool/subagent/duration 摘要
- canonical：`diagnosis.md` · `retrieved_docs.md` · `final_resolution.md` · `ticket_draft.md`（可选）
