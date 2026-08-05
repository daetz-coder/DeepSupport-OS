# DeepSupport OS

**DeepSupport OS is an open-source enterprise IT support agent harness powered by Deep Agents.**

DeepSupport OS 是一个基于 Deep Agents Harness 的开源企业 IT 技术支持智能体。面向 Microsoft 365 企业 IT Help Desk，用 Mock 数据与 Mock MCP 模拟企业系统，突出长任务规划、文件工作区、Skills、Subagents、Memory、Checkpoint 与人工审批。

> 详细实施清单见 [plan.md](./plan.md)。

## 架构概览

```text
用户问题
   ↓
Web UI (Vue3) / API (FastAPI)
   ↓
Deep Agents Harness
   ├── Planning / Filesystem / Skills / Subagents
   ├── Memory / Checkpoint / Human-in-the-loop
   └── Tool Orchestration
         ↓
   Mock MCP Services  ←→  SQLite Mock 企业数据
         ↓
   Knowledge MCP → RAGLab HTTP API（封装调用，不复制代码）
```

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | uv + FastAPI |
| Agent | Deep Agents + LangGraph + LangChain |
| RAG | 调用本地 [RAGLab](../RAGLab) HTTP API |
| 企业系统 | Mock MCP + SQLite + Faker |
| 默认 LLM | DeepSeek（可切换 Ollama） |

## 快速开始

### 前置

- Python 3.12+、[uv](https://github.com/astral-sh/uv)、Node.js 20+
- 本地已有 [RAGLab](../RAGLab) 与 BGE 模型（默认路径 `D:\2026AppDev\RAGLab\models`）
- DeepSeek API Key（或本地 Ollama）；可选 `DAYTONA_API_KEY`（Sandbox）

### 1. 配置

```bash
cp .env.example .env
cp config/mcp_servers.example.json config/mcp_servers.json   # 若尚无
# 编辑 .env：DEEPSEEK_API_KEY、可选 DAYTONA_API_KEY、RAGLAB_BASE_URL=http://127.0.0.1:8001
```

### 2. 本地三进程启动（推荐）

开 **三个终端**（均用 `uv`，无需 `activate`）：

```bash
# 终端 A — RAGLab（外部知识；端口 8001，避免与本仓库 8000 冲突）
cd ../RAGLab
docker compose up -d qdrant          # 首次 / 需要时
cd backend
uv run --python .venv uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 终端 B — DeepSupport 后端
cd backend
uv sync
uv run deepsupport-os
# 或: uv run uvicorn deepsupport_os.main:app --reload --port 8000

# 终端 C — DeepSupport 前端
cd frontend
npm install                          # 首次
npm run dev
```

| 服务 | 地址 |
|---|---|
| DeepSupport UI | http://localhost:5173 |
| DeepSupport API | http://localhost:8000/docs |
| RAGLab API | http://localhost:8001/docs |

打开 UI 后顶部会显示 **后端 / LLM / RAGLab / Sandbox** 状态；可点「检查依赖」刷新。未启 RAGLab 时 Knowledge 回退本地 Markdown；Sandbox 未配置时本地 Skills/工作区仍可用。

### 3. Docker Compose（可选）

```bash
# 需已配置 .env；RAGLab 仍建议宿主机单独运行（容器经 host.docker.internal:8001 访问）
docker compose up --build
# API http://localhost:8000  · 前端 http://localhost:5173（nginx → api）
# 停止：docker compose down
```

**实测记录（2026-08-05 · Windows 10 + Docker Desktop 29.5 / Compose v5.1）**

| 项 | 结果 |
|---|---|
| `docker compose up --build -d` | 成功；首次构建约 3–4 分钟 |
| `api` | `healthy`；`GET /health` → `{"status":"ok"}` |
| `frontend` | 启动正常；`GET /` → 200；经 nginx 代理 `GET /health`、`GET /api/meta/skills` → 200 |
| 卷挂载 | 容器内 `root_dir=/app`；`data` / `skills` / `config` / `memory` 可读 |
| RAGLab | compose 将 `RAGLAB_BASE_URL` 指到 `host.docker.internal:8001`（宿主机未启 RAGLab 时 Knowledge 回退本地 Markdown） |

说明：远程 MCP（`127.0.0.1:8100`）与 Ollama 同理需跑在宿主机；远程开关以 `config/extensions.json`（或 UI「MCP」）为准，不是仅改 `.env` 的 `MCP_REMOTE_ENABLED`。

### Skills（渐进披露 + 持续接入）

- Builtin：`skills/*/SKILL.md`，长 SOP 放 `references/`（L3 按需 `read_file`）
- 公开 skill：`skills/catalog.json` + `scripts/import_skill.py` → `skills/imported/`
- 索引 API：`GET /api/meta/skills`
- 说明：[skills/README.md](./skills/README.md)

### MCP（本地 + 远程）

- 默认：进程内 Mock LangChain 工具（`config/extensions.json` → `mcp_local_tools`）
- 远程：编辑 `config/mcp_servers.json`，并将 `extensions.json` 中 `mcp_remote_enabled` 设为 `true`（或 UI「MCP」）

```bash
# 终端 A — 远程风格 HTTP Employee MCP
cd backend && uv run python -m deepsupport_os.mcp.servers.employee --http

# 终端 B — 连通性冒烟
cd backend && uv run python ../scripts/test_remote_mcp.py
# 或 GET /api/meta/mcp  ·  POST /api/meta/mcp/reload
```

第三方/公开 MCP：在 `mcp_servers.json` 增加 `url` + `transport`（`streamable_http` / `sse`）即可，无需改代码。

## 仓库结构

```text
DeepSupport-OS/
├── backend/          # FastAPI + Deep Agents + MCP client
├── frontend/         # Vue3 + Element Plus
├── skills/           # Builtin + imported Agent Skills
├── config/           # mcp_servers.json（远程 MCP）
├── data/             # SQLite 与语料
├── workspace/        # 任务文件工作区
├── docs/             # 设计与评测；demo-screenshots/
├── scripts/          # import_skill / eval / remote MCP 冒烟
├── plan.md           # 精简待办
├── CONTRIBUTING.md
├── SECURITY.md
└── README.md
```

## 当前状态

Phase 0–11 主链路已可运行（Harness、HITL、Memory/Todo/Artifacts、Daytona sidecar）。Skills SOP + 公开导入 + 远程 MCP 客户端已接入。详见 [plan.md](./plan.md)、[CONTRIBUTING.md](./CONTRIBUTING.md)。

## License

[MIT](./LICENSE)
