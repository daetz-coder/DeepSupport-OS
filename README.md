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
- 本地已有 RAGLab 与 BGE 模型（默认路径 `D:\2026AppDev\RAGLab\models`）
- DeepSeek API Key（或本地 Ollama）

### 1. 配置

```bash
cp .env.example .env
cp config/mcp_servers.example.json config/mcp_servers.json   # 若尚无
# 编辑 .env：DEEPSEEK_API_KEY、可选 DAYTONA_API_KEY、RAGLAB_* 
```

### 2. 后端

```bash
cd backend
uv sync
uv run deepsupport-os
# 或: uv run uvicorn deepsupport_os.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 。API 文档：http://localhost:8000/docs 。

### 4. RAGLab（知识检索，可选）

DeepSupport OS **不内嵌** RAG。另启 RAGLab（默认 `8001`）；未启动时 Knowledge 工具回退本地 Markdown。

### 5. Docker Compose（可选）

```bash
# 需已配置 .env；RAGLab 仍建议宿主机单独运行
docker compose up --build
# API http://localhost:8000  · 前端 http://localhost:5173（映射以 compose 为准）
```

### Skills（渐进披露 + 持续接入）

- Builtin：`skills/*/SKILL.md`，长 SOP 放 `references/`（L3 按需 `read_file`）
- 公开 skill：`skills/catalog.json` + `scripts/import_skill.py` → `skills/imported/`
- 索引 API：`GET /api/meta/skills`
- 说明：[skills/README.md](./skills/README.md)

### MCP（本地 + 远程）

- 默认：进程内 Mock LangChain 工具（`MCP_LOCAL_TOOLS=true`）
- 远程：编辑 `config/mcp_servers.json`，设 `MCP_REMOTE_ENABLED=true`

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
