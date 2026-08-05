# DeepSupport OS — Architecture Fix Backlog

> 来源：2026-08-05 Architecture Review。与 `plan.md` 互补。  
> 进度：`[x]` 已在本迭代落地 · `[ ]` 仍待做

图例：**P0** 立刻影响正确性/可维护性 · **P1** 开源与二开关键 · **P2** 企业化增强

---

## P0 — 正确性 / 架构债

### F-01 Harness 工厂过胖，职责边界不清
- **状态**：`[x]`
- **产出**：`harness/prompts.py`（PromptBundle）· `harness/builder.py`（`HarnessBuilder` + `RuntimePorts`）· `agent.py` 变薄为入口/checkpointer

### F-02 进程内 Mock Tools ≠ MCP 契约，双轨并存
- **状态**：`[x]` 文档/ADR 已落地（实现收敛后置）
- **产出**：[docs/adr/0001-mcp-dual-track.md](./docs/adr/0001-mcp-dual-track.md)；README 用语改为 Local Tool Adapter + Remote MCP

### F-03 Artifact 无 Schema / 无强制校验
- **状态**：`[x]`
- **产出**：`workspace/{tid}/manifest.json`（`write_manifest` / `validate_canonical`）；任务记录带回 `manifest`

### F-04 Memory 仅单文件 AGENTS.md，无语义检索
- **状态**：`[x]` 分层已落地（语义检索仍后置）
- **产出**：`memory/org.md` + `memory/AGENTS.md`；`MEMORY_PATHS` 双路径注入；`harness/memory_files.py`

### F-05 System Prompt 与 Skill/Memory 内容重叠
- **状态**：`[x]`
- **产出**：SYSTEM_PROMPT 仅硬约束；演示账号在 `memory/org.md`；产物约定指向 manifest

---

## P1 — 开源质量 / 二开体验

### F-06 文档与 API 面不同步
- **状态**：`[x]`（截图 F-12 仍空）
- **产出**：重写 `docs/api.md`、`docs/architecture.md`

### F-07 缺少 Agent E2E / HITL resume 自动化测试
- **状态**：`[x]` 部分（无真 LLM invoke；有 HITL apply smoke + contracts）
- **产出**：`test_harness_contracts.py`、`test_hitl_resume_apply_license_and_close`

### F-08 SubAgent Prompt 过薄，委派不稳定
- **状态**：`[x]`
- **产出**：三 SubAgent 增加输入/输出契约与 ERROR 约定

### F-09 Observability 停在 Task JSON Trace
- **状态**：`[x]` 基础版
- **产出**：`workspace/{tid}/metrics.json`（duration / tool_calls / subagents）

### F-10 鲁棒性：缺统一 Retry / Timeout / Circuit
- **状态**：`[x]` 基础版
- **产出**：`core/http_retry.py`；RAGLab client + Remote MCP load 有限重试

### F-11 前端单文件 App.vue（~1.2k 行）
- **状态**：`[x]` 脚本拆分（模板仍聚合）
- **产出**：`types.ts` · `api/client.ts` · `composables/useHealth|useSkills|useMcp.ts`

### F-12 Demo 与开箱体验不完整
- **状态**：`[ ]`（screenshots + benchmark 扩量）

---

## P2 — 企业化 / 能力纵深

F-13 … F-20 仍后置（见原建议）。F-16 部分被 F-03/F-09 覆盖（manifest/metrics）。

---

## 明确不做 / 后置（与 plan.md 对齐）

- 全量 CI/CD — 不做
- 真实 AD / M365 / ServiceNow — 后置
- Baseline C 完整手写 LangGraph — 后置
- F-04 语义 Memory 检索 — 后置
- F-11 模板级组件拆分 — 可选后续

---

## 建议落地顺序（下一迭代）

1. F-12 Demo 截图 / README 开箱路径补全  
2. F-02 MCP 双轨实现收敛（可选）  
3. F-11 继续拆面板组件（可选）
