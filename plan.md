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
- [ ] 其余域独立 FastMCP 进程（按需后补）

---

## Phase 3 — RAGLab 封装

- [x] ~~RAGLabClient + Knowledge 工具 + 4 篇示例 Markdown~~
- [ ] 正式语料经 RAGLab ingest（爬取后置）

---

## Phase 5 — Skills + Subagents

- [x] ~~outlook / account-access / ticket-management~~
- [x] ~~teams / onedrive / office / escalation / resolution-report 骨架~~
- [x] ~~Knowledge Research / Environment Diagnosis / Ticket Operations~~

---

## Phase 4 — Deep Agents Harness

- [x] ~~create_deep_agent + tools + HITL + MemorySaver~~
- [x] ~~MVP Subagents 挂载~~
- [x] ~~持久化 checkpointer（SQLite）~~
- [x] ~~Execution Trace API 完善~~
- [x] ~~HITL 批准后写操作落库~~

---

## Phase 6 — API + 前端

- [x] ~~Tasks API + Vue 提问/轨迹/HITL 壳~~
- [x] ~~SSE 流式进度~~
- [x] ~~工具调用结构化展示~~

---

## Phase 7 — Demo

- [x] ~~Demo：Outlook 登录失败（端到端，已检出 locked + 文档 + HITL）~~
- [x] ~~Demo：账号重置 HITL（approve resume 成功）~~
- [x] ~~Demo：自动创建工单（T1003）~~
- [x] ~~Demo：Checkpoint 持久化恢复（SQLite checkpointer）~~
- [x] ~~其余 Demo 用例数据：`data/benchmark/mvp_cases.jsonl`（8 条起步）~~

---

## Phase 8 — 评测（后置）

- [x] ~~Benchmark 案例格式 + 少量样例（mvp_cases.jsonl）~~
- [ ] 扩充至 ~30 条 + 核心指标采集脚本
- [ ] Baseline 说明文档

---

## 进度日志

| 日期 | Phase | 说明 |
|---|---|---|
| 2026-08-04 | 0–6 | 骨架到 API/UI 已 push |
| 2026-08-04 | 确认项 | 用户确认全部默认决策 |
| 2026-08-04 | 5/7 | Subagents + Skills 补齐；Outlook/HITL/建单 Demo 跑通 |
| 2026-08-04 | P0 | Trace API + SSE + 结构化前端 + HITL 落库 |
