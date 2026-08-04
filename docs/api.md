# API Overview

Base URL: `http://127.0.0.1:8000`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info, `llm_configured` |
| GET | `/health` | Liveness |
| POST | `/admin/seed?force=` | Reseed mock DB |
| GET | `/api/tasks` | List recent tasks |
| POST | `/api/tasks` | Run one harness turn (sync) |
| POST | `/api/tasks/stream` | SSE: `status` / `tool_start` / `tool_end` / `message` / `interrupt` / `done` |
| POST | `/api/tasks/resume` | HITL approve/reject + apply writes |
| GET | `/api/tasks/{task_id}` | Task snapshot (SQLite persisted) |
| GET | `/api/tasks/{task_id}/trace` | Structured execution trace |
| GET | `/api/tasks/meta/audit` | Recent audit log |

OpenAPI: `/docs`.
