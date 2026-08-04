# DeepSupport OS — 实施计划

> DeepSupport OS 是一个基于 Deep Agents Harness 的开源企业 IT 技术支持智能体。  
> 前端：Vue3 + Vite + Element Plus · 后端：uv + FastAPI · RAG：封装调用 RAGLab · 企业系统：Mock MCP

完成一项后将该项改为 `~~删除线~~`。同类任务先做通一种模板，再批量扩展。

---

## 已确认技术选型

| 项 | 决策 |
|---|---|
| 前端 | Vue3 + Vite + Element Plus |
| 后端 | uv + FastAPI |
| Agent | `deepagents`（官方 Harness，不手写 Planner/Filesystem） |
| RAG | **封装调用** `D:\2026AppDev\RAGLab`，不复制其实现 |
| 本地模型 | 复用 RAGLab `models/`（BGE embedding + reranker），不重复下载 |
| Mock 数据 | SQLite + Faker |
| MCP | Mock 工具层 + FastMCP Employee 模板 |
| 默认 LLM | DeepSeek（与 RAGLab 一致，可配置） |
| 向量库 | 跟随 RAGLab：Qdrant（由 RAGLab 侧持有） |
| 开源许可 | MIT（暂定，可改） |

---

## 待你确认（阻塞项）

请尽快回复，避免走偏：

1. **微软支持文档采集**：第一阶段是否允许「仅用少量自建示例 Markdown（模拟 M365 支持文）」跑通链路，正式爬取放到后续并遵守 robots/ToS？（**已按此临时落地 4 篇示例**）
2. **RAG 集成方式**：推荐 **HTTP 调用本地运行的 RAGLab API**（松耦合）。是否同意？（**已按此实现 RAGLabClient + 本地回退**）
3. **推送节奏**：每完成一个 Phase 就 `commit + push`，是否可以？
4. **Human Approval 写操作范围**：默认包含 `request_password_reset` / `request_license_change` / `close_ticket` / `escalate_ticket`，是否够用？
5. **Benchmark 规模**：MVP 先做 ~30 条手工案例，完整 100–300 条后置，是否同意？

---

## Phase 0 — 仓库骨架

- [x] ~~根目录结构：`backend/` `frontend/` `skills/` `data/` `docs/` `scripts/`~~
- [x] ~~`README.md`（中英定位、架构、快速开始）~~
- [x] ~~`.gitignore` / `.env.example` / `LICENSE`（MIT）~~
- [x] ~~后端 `uv` 初始化：`pyproject.toml`、依赖锁定~~
- [x] ~~前端 `npm create vite`：Vue3 + TS + Element Plus 最小壳~~
- [x] ~~`docker-compose.yml` 草案（后置完善）~~
- [x] ~~首次 commit 并 push 到 `git@github.com:daetz-coder/DeepSupport-OS.git`~~

---

## Phase 1 — Mock 企业数据层

- [x] ~~SQLite schema：employees / assets / accounts / licenses / tickets / cases / policies / audit_logs~~
- [x] ~~Faker 种子脚本（可复现 seed）~~
- [x] ~~仓库层 `repositories/`（CRUD，供 MCP 调用）~~
- [x] ~~审计日志写入工具结果~~

---

## Phase 2 — Mock MCP Servers（先做通 1 个模板）

- [x] ~~MCP 公共基座（连接 SQLite、统一错误/审计）~~
- [x] ~~模板：**Employee MCP**（FastMCP + `get_employee` / `get_department` / `get_manager`）~~
- [x] ~~Asset / Account / Ticket / Case / Policy / Notification 工具（同模式 LangChain tools，未再拆独立 FastMCP 进程）~~
- [ ] 其余域独立 FastMCP server 进程（按需后补，避免重复）

---

## Phase 3 — RAGLab 调用封装

- [x] ~~`RAGLabClient`（HTTP 封装 search / get_document）~~
- [x] ~~配置：`RAGLAB_BASE_URL`、模型路径指向 RAGLab `models/`~~
- [x] ~~Knowledge 工具：`search_docs` / `get_document` / `search_cases` + 本地 Markdown 回退~~
- [x] ~~示例知识：4 篇自建 M365 支持 Markdown~~
- [ ] 正式语料入库：通过 RAGLab ingest API（待确认爬取策略）

---

## Phase 4 — Deep Agents Harness 核心

- [x] ~~接入 `create_deep_agent` + DeepSeek ChatOpenAI~~
- [x] ~~挂载 Mock + Knowledge tools~~
- [x] ~~HITL `interrupt_on` 写操作~~
- [x] ~~MemorySaver checkpointer（进程内）~~
- [ ] 持久化 checkpointer（SQLite/Postgres）与 workspace backend 细化
- [ ] Execution Trace API 完善
- [ ] Subagents 挂载（见 Phase 5）

---

## Phase 5 — Skills + Subagents（MVP）

- [x] ~~模板 Skill：`outlook-troubleshooting/SKILL.md`~~
- [x] ~~`account-access` / `ticket-management`~~
- [ ] 其余 Skill 骨架（Teams / OneDrive / Office / Escalation / Report）
- [ ] Knowledge Research / Environment Diagnosis / Ticket Operations Subagents

---

## Phase 6 — API + 前端

- [x] ~~FastAPI：`POST /api/tasks`、`POST /api/tasks/resume`、查询~~
- [x] ~~Vue：提问、轨迹、HITL 批准/拒绝壳~~
- [ ] 流式进度 SSE
- [ ] 计划/工具调用结构化展示

---

## Phase 7 — Demo 任务（先跑通 1 条）

- [ ] Demo：Outlook 登录失败（端到端联调，需 `.env` 中 DeepSeek Key）
- [ ] Demo：账号重置（HITL）
- [ ] Demo：自动创建工单
- [ ] Demo：中断后恢复（Checkpoint）
- [ ] 其余 Demo 骨架

---

## Phase 8 — 评测与基线（后置）

- [ ] Benchmark 案例格式 + 少量样例
- [ ] 核心指标采集
- [ ] Baseline A/B 说明文档

---

## 明确不做 / 延后

- 不连接真实 AD / M365 / ServiceNow
- 不重复下载 embedding/reranker
- 不手写 Planner / Filesystem / Subagent 运行时（用 deepagents）
- 不复制 RAGLab 检索/切分/embedding 源码
- 完整 Benchmark 100–300 与对比实验放到主链路可跑之后

---

## 进度日志

| 日期 | Phase | 说明 |
|---|---|---|
| 2026-08-04 | — | 计划初稿创建 |
| 2026-08-04 | 0 | 骨架完成并 push |
| 2026-08-04 | 1–6 | Mock DB/MCP 工具、RAGLab 封装、Harness、Skills、Tasks API、Vue 壳 |