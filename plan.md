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
| Agent | `deepagents`（官方 Harness） |
| RAG | **HTTP 调用 RAGLab** + 本地示例知识回退 |
| 本地模型 | 复用 RAGLab `models/`，不重复下载 |
| Mock 数据 | SQLite + Faker |
| MCP | Mock 工具层 + FastMCP Employee 模板 |
| 默认 LLM | DeepSeek（本地 `.env`，不入库） |
| 向量库 | RAGLab 侧 Qdrant |
| 知识语料（MVP） | 自建示例 Markdown；正式微软爬取后置 |
| HITL 写操作 | password_reset / license_change / close_ticket / escalate_ticket |
| Benchmark | MVP ~30 条；100–300 后置 |
| 推送节奏 | 每个 Phase `commit + push` |
| 开源许可 | MIT |

---

## ~~待确认阻塞项~~（2026-08-04 已全部确认）

1. ~~微软文档：第一阶段自建 Markdown，正式爬取后置~~ ✅
2. ~~RAG：HTTP 调 RAGLab~~ ✅
3. ~~每 Phase commit + push~~ ✅
4. ~~HITL 四类写操作够用~~ ✅
5. ~~Benchmark MVP ~30~~ ✅
6. ~~DeepSeek Key：从 RAGLab `.env` 复制到本地（不提交）~~ ✅

---

## Phase 0 — 仓库骨架

- [x] ~~根目录结构 / README / gitignore / LICENSE / uv / Vue 壳 / compose 草案 / 首次 push~~

---

## Phase 1 — Mock 企业数据层

- [x] ~~SQLite schema + Faker seed + repositories + audit_logs~~

---

## Phase 2 — Mock MCP

- [x] ~~Employee FastMCP 模板 + 全套 LangChain Mock 工具~~
- [ ] 其余域独立 FastMCP 进程（Account / Ticket / Asset…，按需后补，MVP 不阻塞）

---

## Phase 3 — RAGLab 封装

- [x] ~~RAGLabClient + Knowledge 工具 + 4 篇示例 Markdown~~
- [x] ~~微软公开支持页试采：`scripts/crawl_ms_support.py`（robots + sitemap + 限速）~~
- [x] ~~落地 `data/knowledge/microsoft/*.md`（本地检索已可命中）~~
- [ ] 正式语料批量扩采 + 经 RAGLab ingest 入库（需 RAGLab 在线）

---

## Phase 4 — Deep Agents Harness

- [x] ~~create_deep_agent + tools + HITL + MemorySaver~~
- [x] ~~MVP Subagents 挂载~~
- [x] ~~持久化 checkpointer（SQLite）~~
- [x] ~~Execution Trace API 完善~~
- [x] ~~HITL 批准后写操作落库~~

---

## Phase 5 — Skills + Subagents

- [x] ~~outlook / account-access / ticket-management~~
- [x] ~~teams / onedrive / office / escalation / resolution-report 骨架~~
- [x] ~~Knowledge Research / Environment Diagnosis / Ticket Operations~~

---

## Phase 6 — API + 前端

- [x] ~~Tasks API + Vue 提问/轨迹/HITL 壳~~
- [x] ~~SSE 流式进度~~
- [x] ~~工具调用结构化展示~~
- [x] ~~LLM 未配置告警 / 会话列表 / 审计日志视图~~

---

## Phase 7 — Demo

- [x] ~~Demo：Outlook 登录失败 / HITL / 建单 / Checkpoint~~
- [x] ~~Demo 用例：`data/benchmark/mvp_cases.jsonl`~~

---

## Phase 8 — 评测

- [x] ~~Benchmark 案例格式~~
- [x] ~~扩充至 ~30 条（golden expect）~~
- [x] ~~`scripts/run_eval.py`（offline 通过；online 可选）~~
- [x] ~~Baseline 说明：`docs/baselines.md`~~

---

## Phase 9 — 工程化收尾

- [x] ~~pytest：repositories / hitl_apply / trace / task_store / API smoke（9 passed）~~
- [x] ~~`backend/Dockerfile` + `frontend/Dockerfile`（nginx）+ compose 可构建~~
- [x] ~~docs：architecture / api / demo / baselines~~
- [x] ~~任务记录持久化（`task_records` SQLite）~~
- [x] ~~前端增强：LLM 告警、线程列表、审计视图~~

---

## 代码审查待调整项

- [x] ~~`write_audit` 去掉每次 `init_db()`~~
- [x] ~~`update_ticket` 禁止直接 closed/escalated（需 HITL apply）~~
- [x] ~~`_tasks` 改为 SQLite + 锁（`task_store`）~~
- [x] ~~checkpointer 显式 sqlite3 连接 + atexit 关闭~~
- [x] ~~清理 `backend/data/deepsupport.db` 残留~~

---

## 下一步建议（后续迭代）

1. 微软语料批量扩采 + RAGLab ingest（试采脚本已具备）
2. Online eval 批量跑通与指标看板
3. 按需拆独立 FastMCP 进程 / Compose 生产化

---

## 进度日志

| 日期 | Phase | 说明 |
|---|---|---|
| 2026-08-04 | 0–7 | 主链路与 Demo 可跑 |
| 2026-08-04 | P0 | Trace / SSE / HITL 落库 |
| 2026-08-04 | 走查 | 增补 Phase 8/9 与审查项 |
| 2026-08-04 | 8/9 | 30 条评测、pytest、Docker/docs、任务持久化、前端增强 |
| 2026-08-04 | 语料 | 微软支持页试采（sitemap/robots），落地 microsoft Markdown |
