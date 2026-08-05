# DeepSupport OS

**DeepSupport OS is an open-source enterprise IT support agent harness powered by Deep Agents.**

DeepSupport OS 是一个基于 Deep Agents Harness 的开源企业 IT 技术支持智能体。面向 Microsoft 365 企业 IT Help Desk，用 **Local Tool Adapter（Mock 企业数据）** 与可选 **Remote MCP** 模拟企业系统，突出长任务规划、文件工作区、Skills、Subagents、Memory、Checkpoint 与人工审批。

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
   Local Tool Adapter  ←→  SQLite Mock 企业数据
         ↓
   Knowledge → RAGLab HTTP API（可选 Remote MCP）
```

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | uv + FastAPI |
| Agent | Deep Agents + LangGraph + LangChain |
| RAG | 调用本地 [RAGLab](../RAGLab) HTTP API |
| 企业系统 | Local Tool Adapter（SQLite Mock）+ 可选 Remote MCP |
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
# 编辑 .env：DEEPSEEK_API_KEY、可选 DAYTONA_API_KEY、RAGLAB_BASE_URL=http://127.0.0.1:8001、RAGLAB_KB=deepsupport
# 可选 ADMIN_TOKEN（非空时管理接口需 Header X-Admin-Token；前端可设 VITE_ADMIN_TOKEN）
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

打开 UI 后顶部会显示 **后端 / LLM**（`/health` 秒回）以及 **RAGLab / Sandbox**（`/api/health/deps`）；可点「检查依赖」刷新。未启 RAGLab 时 Knowledge 回退本地 Markdown；Sandbox 未配置时本地 Skills/工作区仍可用。

默认 API 绑定 `127.0.0.1`（不暴露局域网）。Docker 通过 `API_HOST=0.0.0.0` 对外映射。

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
- 远程：编辑 `config/mcp_servers.json`（默认远程 server 为 `enabled: false`），并将 `extensions.json` 中 `mcp_remote_enabled` 设为 `true`（或 UI「MCP」）

```bash
# 终端 A — 远程风格 HTTP Employee MCP
cd backend && uv run python -m deepsupport_os.mcp.servers.employee --http

# 终端 B — 连通性冒烟
cd backend && uv run python ../scripts/test_remote_mcp.py
# 或 GET /api/meta/mcp  ·  POST /api/meta/mcp/reload
```

第三方/公开 MCP：在 `mcp_servers.json` 增加 `url` + `transport`（`streamable_http` / `sse`）即可，无需改代码。

## 一次运行链路（示例：Outlook 登录失败）

```text
用户：我的 Outlook 一直登录不上，邮箱 wei.zhang@contoso.com
  ↓ POST /api/tasks/stream（SSE 进度）
  ↓ get_agent(thread)  → HarnessBuilder → create_deep_agent
  ↓ 系统提示词：先收集上下文 → 规划 → 诊断 → 检索 → 解决
  ├─ write_todos                          # 建立排障计划
  ├─ get_employee / get_account_status / get_device   # 环境诊断
  ├─ search_docs / read_file(/skills/…)   # 知识 + Skill
  ├─ request_password_reset  → HITL 中断  # 等待人工审批
  ├─ apply_approved_writes                # 批准后密码重置落库
  ├─ write_file(final_resolution.md)      # 产物
  └─ notify_user / create_ticket          # 收尾
```

## 评测（Automated Eval）

- **离线**（不调 LLM）：`cd backend && uv run python ../scripts/run_eval.py --offline --from-db`
- **在线**：`uv run python ../scripts/run_eval.py --online --from-db`（可用 `--fast --resume` 加速续跑）
- 指标目录：`GET /api/eval/metrics`
- 说明：[docs/testing.md](./docs/testing.md) · 快照：[docs/eval-results.md](./docs/eval-results.md) · 基线：[docs/baselines.md](./docs/baselines.md)

### 当前指标快照（已跑完 50 案，排除未续跑的余额失败）

| 指标 | 值 | 说明 |
|---|---:|---|
| `pass_rate` | **0.60** | 30/50 通过 |
| `tool_hit_rate` | 0.90 | 工具期望命中 |
| `hitl_hit_rate` | 0.95 | HITL 写工具命中 |
| `planning_hit_rate` | 1.00 | 长任务/复合题 todos |
| `write_safety_rate` | 1.00 | 未绕过 HITL 直接关单/升级 |
| `grounding_rate` | 1.00 | grounding 标签证据工具 |
| `offload_hit_rate` | 0.95 | 工作区 offload |
| `subagent_hit_rate` | **0.00** | 子代理委派短板 |
| `long_task_pass_rate` | 0.29 | 长任务整案通过偏低 |
| `error_rate` | 0.24 | 硬错误（多为递归上限） |
| `p50` / `p95` ms | 16s / 77s | 耗时分布 |

Offline schema：**150/150**。Pytest：**61 passed**。完整表格与 `by_tag` 见 [docs/eval-results.md](./docs/eval-results.md)。
（含 `--fast`：Skill/RAGLab 路径被简化，`skill_hit` 偏乐观，不宜当作生产全量分。）

## 知识管线（本地语料 → RAGLab KB）

```bash
# 抓取 Microsoft 支持文档 → data/knowledge/microsoft/*.md（已 gitignore，可再生成）
cd backend && uv run python ../scripts/crawl_ms_support.py --per-product 30

# 导入 RAGLab（KB 名由 RAGLAB_KB=deepsupport 指定，与共享实例上的其它语料隔离）
uv run python ../scripts/ingest_to_raglab.py

# 在共享 RAGLab 实例上迁移 / 重命名 KB
uv run python ../scripts/migrate_ms_kb.py
```

## 文档地图

| 文档 | 内容 |
|---|---|
| [docs/architecture.md](./docs/architecture.md) | 架构分层 + 模块地图 + 线程生命周期 |
| [架构图](./docs/architecture/deepsupport-os-architecture.svg) | 系统架构图（draw.io 源在 `.drawio-tmp/`，本地交付物） |
| [案例图](./docs/architecture/case-*.svg) | Outlook+HITL 审批 / ask_user 多轮 / 在线评测 / Docker 拓扑 |
| [docs/api.md](./docs/api.md) | HTTP API |
| [docs/testing.md](./docs/testing.md) | 评测指标与落库 |
| [docs/baselines.md](./docs/baselines.md) | 评测基线设计 |
| [docs/eval-results.md](./docs/eval-results.md) | 评测指标快照 |
| [docs/adr/](./docs/adr/) | 架构决策记录 |
| [fix.md](./fix.md) | 架构债 backlog |
| [plan.md](./plan.md) | 产品待办 |

## 仓库结构

```text
DeepSupport-OS/
├── backend/          # FastAPI + Deep Agents + MCP client
├── frontend/         # Vue3 + Element Plus
├── skills/           # Builtin + imported Agent Skills
├── config/           # mcp_servers.json（远程 MCP）
├── data/             # SQLite 与语料
├── workspace/        # 任务文件工作区
├── docs/             # 设计与评测；adr/；demo-screenshots/
├── scripts/          # import_skill / eval / remote MCP 冒烟
├── plan.md           # 精简产品待办
├── fix.md            # 架构债 backlog
├── CONTRIBUTING.md
├── SECURITY.md
└── README.md
```

## 当前状态

Phase 0–11 主链路已可运行（Harness、HITL、Memory/Todo、Artifacts+manifest/metrics、Daytona sidecar）。Skills SOP + 公开导入 + 远程 MCP + RAGLab `kb=deepsupport` 已接入。Benchmark：**150** 用例；offline **150/150**；online 已跑样本 **pass_rate≈0.60**（详见 [docs/eval-results.md](./docs/eval-results.md)）。架构债见 [fix.md](./fix.md)；产品待办见 [plan.md](./plan.md)。

## License

[MIT](./LICENSE)
