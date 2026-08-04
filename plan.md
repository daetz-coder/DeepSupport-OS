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
| MCP | Mock MCP Server（FastMCP / mcp 官方 SDK） |
| 默认 LLM | DeepSeek（与 RAGLab 一致，可配置） |
| 向量库 | 跟随 RAGLab：Qdrant（由 RAGLab 侧持有） |
| 开源许可 | MIT（暂定，可改） |

---

## 待你确认（阻塞项）

请尽快回复，避免走偏：

1. **微软支持文档采集**：第一阶段是否允许「仅用少量自建示例 Markdown（模拟 M365 支持文）」跑通链路，正式爬取放到后续并遵守 robots/ToS？
2. **RAG 集成方式**：推荐 **HTTP 调用本地运行的 RAGLab API**（松耦合）。是否同意？还是希望把 RAGLab 以 path 依赖 import？
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
- [ ] 首次 commit 并 push 到 `git@github.com:daetz-coder/DeepSupport-OS.git`

---

## Phase 1 — Mock 企业数据层

同类任务只做通一套 schema + seed，再扩展表。

- [ ] SQLite schema：employees / assets / accounts / licenses / tickets / cases / policies / audit_logs
- [ ] Faker 种子脚本（可复现 seed）
- [ ] 仓库层 `repositories/`（CRUD，供 MCP 调用）
- [ ] 审计日志写入工具结果

---

## Phase 2 — Mock MCP Servers（先做通 1 个模板）

先完整实现 **Employee MCP** 作为模板，其余按同一模式复制扩展。

- [ ] MCP 公共基座（连接 SQLite、统一错误/审计）
- [ ] ✅ 模板：**Employee MCP**（`get_employee` / `get_department` / `get_manager`）
- [ ] Asset MCP
- [ ] Account MCP（含写操作 + 审批标记）
- [ ] Ticket MCP
- [ ] Case MCP
- [ ] Policy MCP
- [ ] Notification MCP
- [ ] Knowledge MCP（内部转调 RAG 封装，见 Phase 3）

---

## Phase 3 — RAGLab 调用封装

- [ ] `backend/app/rag/`：`RAGLabClient`（HTTP 封装 search / get_document）
- [ ] 配置：`RAGLAB_BASE_URL`、模型路径指向 RAGLab `models/`
- [ ] Knowledge MCP：`search_docs` / `get_document` / `search_cases`
- [ ] 示例知识：少量自建 M365 支持 Markdown（待确认是否可爬取）
- [ ] 入库：通过 RAGLab ingest API 或脚本触发（不复制 chunk/embed 代码）

---

## Phase 4 — Deep Agents Harness 核心

- [ ] 安装并接入 `deepagents`：`create_deep_agent`
- [ ] 工作区 `workspace/`：task_plan / diagnosis / tool_results / final_resolution
- [ ] 挂载 Mock MCP tools
- [ ] Checkpoint（LangGraph checkpointer）
- [ ] HITL interrupt 配置（写操作）
- [ ] Execution Trace 落库 / 文件

---

## Phase 5 — Skills + Subagents（MVP）

Skills：先写通 1 个，再扩展同类。

- [ ] 模板 Skill：`outlook-troubleshooting/SKILL.md`
- [ ] `account-access` / `ticket-management`（优先）
- [ ] 其余 Skill 骨架（Teams / OneDrive / Office / Escalation / Report）— 内容可后补

Subagents（MVP 3 个）：

- [ ] Knowledge Research Agent
- [ ] Environment Diagnosis Agent
- [ ] Ticket Operations Agent

---

## Phase 6 — API + 前端

- [ ] FastAPI：创建任务 / 流式进度 / 审批 / 恢复 / 历史
- [ ] Vue 页面：提问、计划进度、工具调用轨迹、HITL 审批、结果报告
- [ ] 简单即可，不追求复杂仪表盘

---

## Phase 7 — Demo 任务（先跑通 1 条）

先完整跑通 **Outlook 登录失败**，再扩展其余。

- [ ] Demo：Outlook 登录失败
- [ ] Demo：账号重置（HITL）
- [ ] Demo：自动创建工单
- [ ] Demo：中断后恢复（Checkpoint）
- [ ] 其余 Demo（Teams / OneDrive / Office / 复合故障）骨架 + 用例数据

---

## Phase 8 — 评测与基线（后置，不阻塞主链路）

- [ ] Benchmark 案例格式 + 少量样例
- [ ] 核心指标采集：Task Success / Plan Completion / Checkpoint Recovery / Write Safety
- [ ] Baseline A/B 说明文档（实现可后置）

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
| 2026-08-04 | — | 计划初稿创建，等待阻塞项确认 |
| 2026-08-04 | 0 | 仓库骨架、FastAPI/Vue 壳、依赖与 README 完成；待首次 push |
