# `api/`

FastAPI 路由层：对外 HTTP / SSE，不组装 Agent 业务细节（委托 `harness/`）。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 组装 `api_router`（`/api`），挂载 tasks / meta / eval |
| `tasks.py` | 主链路：创建任务、`/stream`、`/resume/stream`、线程列表/删除、产物与审计；`get_agent` 按 thread 缓存（上限 48） |
| `sse_framing.py` | SSE 帧：`SseSequencer` 为事件加单调 `seq` + `run_id` / `thread_id` |
| `trace.py` | 从 LangChain/LangGraph 消息构建执行轨迹；序列化消息、提取 interrupt 信息 |
| `meta.py` | Skills / MCP / Tool / SubAgent 启停与导入的管理 API |
| `eval.py` | 评测目录：用例同步、跑分、查询 runs / metrics |
| `auth.py` | 可选管理员鉴权 `require_admin`（`X-Admin-Token` ↔ `ADMIN_TOKEN`） |

## 入口关系

```text
POST /api/tasks/stream  → tasks.get_agent → harness.build_support_agent
resume                  → hitl_runtime.prepare_resume → hitl_apply
GET  /api/meta/*        → skills_registry / remote_client / capability_registry
POST /api/eval/*        → eval_store (+ scripts 在线评测)
```
