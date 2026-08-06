# `deepsupport_os`

企业 IT 支持 Agent Harness 的 Python 包根目录（`backend/src/deepsupport_os/`）。

## 本层文件

| 文件 | 作用 |
|------|------|
| `__init__.py` | 包版本 `__version__`；CLI `main()` 用 uvicorn 启动应用 |
| `main.py` | FastAPI 工厂 `create_app`：生命周期 `init_db`+seed、CORS、挂载 `/api`；`/`、`/health`、`/admin/seed` 等 |

## 子包

| 目录 | 职责 |
|------|------|
| [`api/`](./api/) | HTTP：任务 SSE、HITL resume、Skills/MCP 元数据、评测 |
| [`harness/`](./harness/) | Deep Agents 组装：prompt、HITL、workspace、memory、backend |
| [`mcp/`](./mcp/) | 本地 Mock 工具 + 远程 MCP 客户端；可选 FastMCP 模板 |
| [`db/`](./db/) | SQLite ORM、仓储、种子、任务/评测落库 |
| [`rag/`](./rag/) | RAGLab HTTP + 知识检索 LangChain 工具 |
| [`core/`](./core/) | 配置、扩展开关、HTTP 重试 |

更细的阅读顺序见仓库 `docs/annotated/reading-map.md`。
