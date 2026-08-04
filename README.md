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
# 编辑 .env，填入 DEEPSEEK_API_KEY，并确认 RAGLAB_* / 模型路径
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

### 4. RAGLab（知识检索）

DeepSupport OS **不内嵌** RAG 实现。请另行启动 RAGLab（默认约定端口 `8001`），由 Knowledge MCP 通过 HTTP 调用。

## 仓库结构

```text
DeepSupport-OS/
├── backend/          # FastAPI + Deep Agents + Mock MCP
├── frontend/         # Vue3 + Element Plus
├── skills/           # Agent Skills (SKILL.md)
├── data/             # SQLite 与示例数据
├── workspace/        # 任务文件工作区
├── docs/             # 设计与评测文档
├── scripts/          # 种子数据 / 运维脚本
├── plan.md           # 实施计划（完成项划线）
└── README.md
```

## 当前状态

Phase 0–7 主链路已可运行：Mock 企业数据、MCP 工具、RAGLab HTTP 封装、Deep Agents Harness（Skills / Subagents / HITL / SQLite Checkpoint）、Tasks API 与 Vue 壳。详见 [plan.md](./plan.md)。

本地需配置 `.env`（可从 RAGLab 复制 DeepSeek Key，**不要提交**）。

## License

[MIT](./LICENSE)
