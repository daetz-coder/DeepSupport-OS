# DeepSupport OS — 实施计划

> DeepSupport OS 是一个基于 Deep Agents Harness 的开源企业 IT 技术支持智能体。  
> 前端：Vue3 + Vite + Element Plus · 后端：uv + FastAPI · RAG：封装调用 RAGLab · 企业系统：Mock MCP

完成一项后将该项改为 `~~删除线~~`。同类任务先做通一种模板，再批量扩展。

---

## 已确认技术选型


| 项         | 决策                                                               |
| --------- | ---------------------------------------------------------------- |
| 前端        | Vue3 + Vite + Element Plus                                       |
| 后端        | uv + FastAPI                                                     |
| Agent     | `deepagents`（官方 Harness）                                         |
| RAG       | **HTTP 调用 RAGLab** + 本地示例知识回退                                    |
| 本地模型      | 复用 RAGLab `models/`，不重复下载                                        |
| Mock 数据   | SQLite + Faker                                                   |
| MCP       | Mock 工具层 + FastMCP Employee 模板                                   |
| 默认 LLM    | DeepSeek（本地 `.env`，不入库）                                          |
| 向量库       | RAGLab 侧 Qdrant                                                  |
| 知识语料（MVP） | 微软公开支持页 ~50+ 篇 + RAGLab 向量入库；本地 MD fallback                        |
| 沙箱        | Daytona（`DAYTONA_SANDBOX_NAME=deepsupport-sandbox`）               |
| HITL 写操作  | password_reset / license_change / close_ticket / escalate_ticket |
| Benchmark | MVP ~30 条；100–300 后置                                             |
| 推送节奏      | 每个 Phase `commit + push`                                         |
| 开源许可      | MIT                                                              |


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

- ~~根目录结构 / README / gitignore / LICENSE / uv / Vue 壳 / compose 草案 / 首次 push~~

---

## Phase 1 — Mock 企业数据层

- ~~SQLite schema + Faker seed + repositories + audit_logs~~

---

## Phase 2 — Mock MCP

- ~~Employee FastMCP 模板 + 全套 LangChain Mock 工具~~
- 其余域独立 FastMCP 进程（Account / Ticket / Asset…，按需后补，MVP 不阻塞）

---

## Phase 3 — RAGLab 封装

- ~~RAGLabClient + Knowledge 工具 + 4 篇示例 Markdown~~
- ~~微软公开支持页试采：`scripts/crawl_ms_support.py`（robots + sitemap + 限速）~~
- ~~落地 `data/knowledge/microsoft/*.md`（本地检索已可命中）~~
- ~~正式语料批量扩采 + 经 RAGLab ingest 入库（需 RAGLab 在线）~~

---

## Phase 4 — Deep Agents Harness

- ~~create_deep_agent + tools + HITL + MemorySaver~~
- ~~MVP Subagents 挂载~~
- ~~持久化 checkpointer（SQLite）~~
- ~~Execution Trace API 完善~~
- ~~HITL 批准后写操作落库~~

---

## Phase 5 — Skills + Subagents

- ~~outlook / account-access / ticket-management~~
- ~~teams / onedrive / office / escalation / resolution-report 骨架~~
- ~~Knowledge Research / Environment Diagnosis / Ticket Operations~~

---

## Phase 6 — API + 前端

- ~~Tasks API + Vue 提问/轨迹/HITL 壳~~
- ~~SSE 流式进度~~
- ~~工具调用结构化展示~~
- ~~LLM 未配置告警 / 会话列表 / 审计日志视图~~

---

## Phase 7 — Demo

- ~~Demo：Outlook 登录失败 / HITL / 建单 / Checkpoint~~
- ~~Demo 用例：`data/benchmark/mvp_cases.jsonl~~`

---

## Phase 8 — 评测

- ~~Benchmark 案例格式~~
- ~~扩充至 ~30 条（golden expect）~~
- `~~scripts/run_eval.py`（offline 通过；online 可选）~~
- ~~Baseline 说明：`docs/baselines.md`~~

---

## Phase 9 — 工程化收尾

- ~~pytest：repositories / hitl_apply / trace / task_store / API smoke（9 passed）~~
- ~~`backend/Dockerfile` + `frontend/Dockerfile`（nginx）+ compose 可构建~~
- ~~docs：architecture / api / demo / baselines~~
- ~~任务记录持久化（`task_records` SQLite）~~
- ~~前端增强：LLM 告警、线程列表、审计视图~~

---

## 代码审查待调整项

- ~~`write_audit` 去掉每次 `init_db()`~~
- ~~`update_ticket` 禁止直接 closed/escalated（需 HITL apply）~~
- ~~`_tasks` 改为 SQLite + 锁（`task_store`）~~
- ~~checkpointer 显式 sqlite3 连接 + atexit 关闭~~
- ~~清理 `backend/data/deepsupport.db` 残留~~

---

## 下一步建议（后续迭代）

1. Online eval + Baseline A/B 对比（体现 Harness 价值）
2. Workspace 按 thread_id 绑定 + Subagent Trace 标记
3. Compose 实测 / CI / CONTRIBUTING

---

## Phase 10 — 建议后续步骤（待开工）

> MVP 主链路已闭环。下面按价值排序，作为下一轮迭代清单。

### A. 知识与 RAG（优先）

- ~~微软语料扩采：seeds 扩采至 ~50+ 篇（sitemap 超时则回退 seeds）~~
- ~~RAGLab ingest 打通：`scripts/ingest_to_raglab.py`；Knowledge 优先 RAGLab、本地 MD fallback~~
- ~~语料质量门禁：`scripts/check_knowledge_quality.py`（最短正文 / source_url / product；dry-run 报告）~~
- ~~更新选型表：「知识语料」改为“公开支持页 + RAGLab 向量库”~~

### B. 评测与对比实验（体现 Harness 价值）

- Online eval：`run_eval.py --online --limit 30` 实跑并落盘 `last_eval.json`（成功率 / HITL / 工具命中 / 耗时）
- 实现 Baseline A（仅 RAG）与 Baseline B（无 Skills/Subagents 的 tool agent）最小可跑脚本
- 对比表写入 `docs/baselines.md`（Task Success、Long-task、HITL Safety、Token/时延）
- Benchmark 向 100 条扩展（后置到 300）

### C. Harness / Agent 能力加深

- ~~Daytona 沙箱：`DAYTONA_*` + `DaytonaSandbox` 作为 Deep Agents backend（Skills/工作区隔离）~~
- Workspace 后端显式绑定任务目录（`workspace/{thread_id}/`），强化 context offloading 可观测
- Subagent 委派在 Trace 中单独标记（knowledge-research / environment-diagnosis / ticket-operations）
- Skills 从骨架补全为可执行 SOP（Teams / OneDrive / Office 关键步骤与工具名对齐）
- ~~HITL 前端展示 pending 写操作参数预览（邮箱、ticket_id、许可证类型）~~

### D. 产品与开源体验

- `docker compose up` 实测与 README 一键启动说明（含 RAGLab 可选依赖）
- CONTRIBUTING / SECURITY 短文；截图或 GIF 放入 `docs/demo-screenshots/`
- ~~前端：计划待办（todo list）可视化；错误态与重试按钮~~
- CI：GitHub Actions 跑 `pytest` + `run_eval.py --offline`

### E. 明确可继续后置

- 各业务域独立 FastMCP 进程（当前 LangChain 工具层已够用）
- 真实 AD / M365 / ServiceNow 连接
- 微软语料超大规模爬取与版权合规法务审阅

---

## 进度日志


| 日期         | Phase | 说明                                               |
| ---------- | ----- | ------------------------------------------------ |
| 2026-08-04 | 0–7   | 主链路与 Demo 可跑                                     |
| 2026-08-04 | P0    | Trace / SSE / HITL 落库                            |
| 2026-08-04 | 走查    | 增补 Phase 8/9 与审查项                                |
| 2026-08-04 | 8/9   | 30 条评测、pytest、Docker/docs、任务持久化、前端增强             |
| 2026-08-04 | 语料    | 微软支持页试采（sitemap/robots），落地 microsoft Markdown    |
| 2026-08-04 | 规划    | 增补 Phase 10 后续步骤（RAG 扩采 / Online eval / CI / 体验） |
| 2026-08-04 | 10A/C | 微软语料扩采+RAGLab ingest 52 篇；Daytona 沙箱接入 Deep Agents |
| 2026-08-04 | 10C/D | HITL 参数预览、错误重试、计划清单；语料质量门禁脚本 |


