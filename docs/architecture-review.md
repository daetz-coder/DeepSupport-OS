# DeepSupport-OS · Architecture Review

> **角色**：Principal Software Architect / Deep Agents · LangGraph · MCP · FastAPI · 企业 Agent 平台  
> **日期**：2026-08-05  
> **范围**：Harness 全栈（Lifecycle / State / HITL / Workspace / Memory / Tool / Streaming / Multi-thread）  
> **原则**：不修表面 Bug；寻找架构风险与隐藏不一致  
> **关联**：既有 backlog 见根目录 `fix.md`；本文件为更深一层 Lifecycle / 双写 / SoT 审查

---

## 0. Executive Verdict

项目在 **HITL 写路径上已具备「Tool = Intent、API = Apply」的雏形**（`respond` + `when` 守卫），比典型「Tool 直接写库 + interrupt 装饰」更接近企业 Harness。

但整体仍是 **MVP Harness 伪装成企业 Runtime**：

| 维度 | 现状 |
|---|---|
| Exactly Once | 仅部分 HITL 写工具；`create_ticket` / 并发 / `approve` fallback 未闭环 |
| Single Source of Truth | Checkpoint / Workspace / Memory / Enterprise DB / Audit **五套并存且边界模糊** |
| Thread Isolation | Workspace ✅；Memory ❌；Daytona ❌；Enterprise DB ❌ |
| Prompt vs Code | 大量正确性依赖 SYSTEM_PROMPT / SubAgent Prompt |
| Observability | 有 metrics/trace JSON；无 Tracing / Rollback / 统一 Retry |

**Architecture Score：5.5 / 10**

（正确性骨架 6.5；隔离与企业级能力 4.0；可扩展性 5.0 → 综合 5.5）

---

## 1. 发现清单（按等级）

---

### AR-01 · Memory 伪 Long-term：全局共享、无 Thread 隔离

**【等级】** Critical  

**【模块】** Memory / Multi-thread / Context  

**【问题】**  
`/memory/org.md` 与 `/memory/AGENTS.md` 是进程级全局文件（`harness/memory_files.py` → `MEMORY_PATHS`）。所有 `thread_id` 共享同一物理路径；Agent 可向 `AGENTS.md` 追加「会话笔记」，直接串线到其它会话。

**【原因】**  
Deep Agents MemoryMiddleware 按虚拟路径注入；当前实现把「组织事实」与「会话记忆」都挂在固定全局路径，未做 `memory/{tid}/` 或 Store 分片。

**【影响】**  
- Thread A 的诊断结论污染 Thread B 的上下文  
- 多用户并发时 Memory 成为隐式全局状态总线  
- 「会话记忆」名义上是 Long-term，实际是跨租户脏共享

**【为什么违反 Deep Agents / LangGraph 原则】**  
- Deep Agents：Memory 应是 **可寻址、可作用域** 的长期知识；会话态应落 Checkpoint / Workspace  
- LangGraph：`thread_id` 是隔离单元；跨 thread 可变共享态破坏 checkpoint 语义

**【推荐修复】**  
1. `org.md` → 真正只读 org Store（或 `/memory/org.md` 只读挂载）  
2. `AGENTS.md` → `/memory/threads/{tid}/AGENTS.md` 或放弃文件 Memory，改用 Checkpoint + Workspace  
3. 禁止 Agent 写 org；会话笔记写入 Workspace 或 per-thread Memory

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是（任何新「共享文件 Memory」都会复发）

---

### AR-02 · Filesystem Backend 根 = 整个 Repo（伪 Virtual FS）

**【等级】** Critical  

**【模块】** Workspace / Filesystem / Security  

**【问题】**  
`LocalShellBackend(root_dir=settings.root_dir)` 以仓库根为 FS 根。线程隔离仅靠 Prompt 约定「必须写 `/workspace/<tid>/`」，代码层无强制 chroot。Agent 理论上可 `write_file` / `execute` 触及 `skills/`、`memory/`、`data/`、源码。

**【原因】**  
Skills / Memory 需要同一 Backend 可读；用整仓 root 换取便利，未做 Composite 路由强制隔离。

**【影响】**  
- Prompt 被绕过 → 跨 thread 读写 Workspace  
- 企业部署时任意文件读写风险  
- 「Virtual Filesystem」名不副实

**【为什么违反 Deep Agents 原则】**  
Deep Agents Backend 应可切换、可按路由隔离；Workspace 必须是 **强制** thread 沙箱，不能靠 Prompt。

**【推荐修复】**  
```text
CompositeBackend:
  /workspace/  → ThreadScopedBackend(workspace/{tid}/)   # 可写
  /skills/     → ReadOnlyBackend(skills/)
  /memory/     → ScopedMemoryBackend(...)
  /sandbox/    → Daytona (已有)
```
禁止 default 落到整仓可写根。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-03 · SubAgent 挂载写工具 + 仅靠 Prompt 禁止（职责泄漏）

**【等级】** Critical  

**【模块】** Agent Runtime / SubAgent / Tool / HITL  

**【问题】**  
`environment-diagnosis` 工具集 = `EMPLOYEE + ACCOUNT + ASSET`，其中 `ACCOUNT_TOOLS` 含 `request_password_reset` / `request_license_change`。Prompt 写「禁止重置密码」，但 **工具仍可调用并触发 HITL**。  
`ticket-operations` 持有 `escalate_ticket` / `close_ticket` / `create_ticket`，与 Main Agent 工具集重叠。

**【原因】**  
按「领域工具包」整包注入，未按 SubAgent 职责裁剪只读子集。

**【影响】**  
- Main / Sub 均可发起同一写意图 → 重复审批 / 重复 pending  
- 违反「Main 不做 Sub 的工作；Sub 不做写落库」的分层  
- Prompt 成为唯一闸门 → AR-10

**【为什么违反 Deep Agents 原则】**  
SubAgent 应是 **能力收缩的专家**；写副作用必须由单一执行面（HITL Apply 或专用 Write Agent）承担，且工具面必须代码裁剪，不能靠文案。

**【推荐修复】**  
- `environment-diagnosis`：仅 `get_*` 只读工具  
- `ticket-operations`：可保留 `create/update`；终态写仍走 Main+HITL，或明确「唯一写入口」  
- Main：编排 + HITL 写意图；禁止堆长检索（已有 Prompt，需加工具配额/中间件）

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-04 · `approve` Fallback = 潜在双写时间炸弹（Single Executor 脆弱）

**【等级】** Critical（当前多为 High；一旦 Tool 加 apply 即 Critical）  

**【模块】** HITL / Lifecycle / Double Write  

**【问题】**  
`_hitl_resume_decisions`：apply 成功 → `respond`（跳过 Tool）；apply 失败或 empty → `{"type":"approve"}`，**LangGraph 会再次执行 Tool**。  
当前 Tool 只返回 `pending_approval` 不写库，故暂无业务双写。但：

1. 架构上存在 **两条执行路径**（API Apply vs Tool re-run）  
2. 未来任何人在 Tool 内加 `apply_*` → 立即 Double Write  
3. apply 部分失败时：UI「已批准」与 DB 不一致，且 Tool 重跑仍可能只返回 pending

**【原因】**  
用 `approve` 作容错回退，未坚持「唯一执行者 = `apply_approved_writes`」。

**【影响】**  
生命周期语义分裂；Exactly Once 无法在协议层保证。

**【为什么违反 LangGraph / HITL 原则】**  
HITL 批准后应对 **已决定的副作用** 做 commit，再 `respond` 注入结果；`approve` 语义是「允许工具执行」——与「API 已执行」互斥。二者并存 = 双执行者。

**【推荐修复】**  
- **禁止** HITL resume 使用 `approve`  
- apply 失败 → `reject` + 明确错误 ToolMessage，或专用 `respond` 错误载荷  
- Tool 层永远 Intent-only；用类型/lint/测试锁定「WRITE_TOOLS 不得调用 apply_*」

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是（极高）

---

### AR-05 · `create_ticket` 即时写库、无幂等键（绕过 HITL 模型）

**【等级】** High  

**【模块】** Tool / Idempotency / Lifecycle  

**【问题】**  
`create_ticket` 调用即 `INSERT`；`ticket_id = T{1000+count+1}` 基于全局 count，并发不安全。Main 与 `ticket-operations` 均可创建 → 同一用户意图可开多张单。无 `client_request_id` / idempotency key。

**【原因】**  
「开单」被视为低风险，未纳入 `interrupt_on` / Intent 模式。

**【影响】**  
重复开单、ID 竞态、与 HITL 写模型不一致；扩展工单系统时必重构。

**【推荐修复】**  
- Intent：`draft_ticket` → Workspace；确认后 `commit_ticket`  
- 或：`create_ticket(idempotency_key=...)` 唯一约束  
- ID 用 UUID / sequence，禁止 count+1

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-06 · `apply_*` 非真正幂等；并发无锁

**【等级】** High  

**【模块】** Idempotency / Multi-thread / Enterprise DB  

**【问题】**  
- `apply_password_reset`：已是 `active` 仍再次 commit（无 `already_applied` 短路写）  
- `apply_license_change`：无条件覆盖 license  
- `update_ticket(allow_terminal=True)`：可从 closed 再写其它字段；无乐观锁 / 版本号  
- 多 thread 对同一 email/ticket 并行 HITL → last-write-wins  

**【原因】**  
Mock SQLite Repo 无领域事件 / 版本 / 幂等表。

**【影响】**  
At-Least-Once resume、重复点击批准、双线程审批 → 不确定副作用。

**【为什么违反企业 Agent 原则】**  
写操作必须 Exactly Once：以 **业务状态机 + 幂等键** 保证，不能依赖「用户只点一次」。

**【推荐修复】**  
```text
apply_*(..., approval_id / idempotency_key)
→ INSERT INTO applied_actions(key) UNIQUE
→ 状态机校验 (locked→active)
→ 否则返回 already_applied
```

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-07 · Daytona / Hybrid Backend 进程级单例串线

**【等级】** High  

**【模块】** Workspace / Multi-thread / Filesystem  

**【问题】**  
`_hybrid_backend` / `_daytona_raw` / sandbox 名 `deepsupport-sandbox` 全局单例。所有 thread 共享同一 `/sandbox/` 与同一远端沙箱。

**【原因】**  
sidecar 为省成本复用 sandbox，未按 thread 创建。

**【影响】**  
Thread A 的 sandbox 文件被 B 看见/覆盖；`run_sandbox_shell` 无租户隔离。

**【推荐修复】**  
- 默认禁用共享可写 sandbox；或 `sandbox_name = f"ds-{hash(tid)}"`  
- Hybrid backend **不要** 进程级缓存跨 thread；至少按 thread 路由

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-08 · 删除 Thread 不清理 Checkpoint / 企业写副作用

**【等级】** High  

**【模块】** Lifecycle / Recover / State  

**【问题】**  
`DELETE /threads/{id}`：清 task_store + agent 缓存 + `rmtree(workspace)`；**不删** `checkpoints.sqlite` 中该 thread 行；**不回滚** 已 HITL 落库的 Account/Ticket。

**【原因】**  
删除被当作「UI 会话清理」，未定义为 Runtime 资源回收。

**【影响】**  
同 thread_id 重建 → 幽灵 checkpoint 恢复旧中断态；企业数据与会话生命周期脱节。

**【推荐修复】**  
明确两种 API：  
- `archive_thread`：保留 checkpoint + audit  
- `purge_thread`：删 checkpoint + workspace + 可选补偿事件  

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-09 · Checkpoint / Workspace / Memory / DB / Audit = Multiple Sources of Truth

**【等级】** High  

**【模块】** State  

**【问题】**  

| 数据 | 存放 | 作用域 | 问题 |
|---|---|---|---|
| 对话/todos/中断 | Checkpoint | thread | SoT ✅ |
| 排障产物 | Workspace | thread | 与消息摘要可能漂移 |
| 组织/会话笔记 | Memory 文件 | **全局** | 与 Checkpoint 重复且串线 |
| 账号/工单真相 | deepsupport.db | **全局** | 与 Tool 返回 / pending 可能短暂不一致 |
| 审计 | AuditLog | 全局（task_id 常为 `adhoc`） | Tool audit + hitl_apply 双记；task 关联弱 |
| 运行概览 | task_store / overview | thread | 由 trace 派生，非权威 |

**【原因】**  
分层文档写了意图，缺强制「写路径契约」。

**【影响】**  
UI / Agent / DB 三方对「是否已重置密码」可能短暂或永久不一致。

**【推荐修复】**  
颁布 State Contract：  
- **业务真相**：Enterprise DB（仅 Apply 可写）  
- **运行真相**：Checkpoint  
- **产物**：Workspace（派生，可重建）  
- **Memory**：仅 org 只读；会话态禁止进全局 Memory  
- **Audit**：append-only，带 `thread_id` + `approval_id`

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-10 · 正确性高度依赖 Prompt（架构气味）

**【等级】** High  

**【模块】** Prompt / Agent Runtime  

**【问题】**  
以下仅靠 `SYSTEM_PROMPT` / SubAgent prompt，无中间件硬约束：  
- 每轮必须 `write_todos`  
- 必须委派三 SubAgent  
- 禁止声称未批准已写入  
- 禁止重复 `ask_user`  
- SubAgent 禁止写操作  
- 工作区路径必须用虚拟路径  

**【原因】**  
Harness 把「策略」放在 Prompt，把「机制」留在少数 HITL/`when`。

**【影响】**  
模型漂移 / 换模型 / 评测压力下行为崩溃；Bug 只能改 Prompt → 说明架构失守。

**【为什么违反原则】**  
Prompt 只能增强；**机制**（工具裁剪、middleware、状态机）必须保证正确。

**【推荐修复】**  
- 工具白名单按角色（已部分）  
- `before_tool` middleware：缺 todos 拒绝其它工具；重复 ask 检测  
- 写工具仅 Main + Intent  

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-11 · Audit `task_id="adhoc"` + 双记，可观测性不足

**【等级】** Medium  

**【模块】** Tool / Observability / Audit  

**【问题】**  
`_audit(..., task_id="adhoc")` 默认；知识工具亦 `adhoc`。HITL 另写 `hitl_apply:*`。`_recent_audit()` 默认全局最近 30 条，跨 thread 混杂。无 OpenTelemetry span；无 rollback 记录。

**【原因】**  
Tool 层无 Runtime Context（thread_id/task_id）注入。

**【影响】**  
无法按 thread 审计；合规与排障困难。

**【推荐修复】**  
`contextvars` 注入 `thread_id`/`task_id`/`run_id`；统一 Audit schema；对接 OTel。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-12 · Agent 缓存 FIFO + 全局 `tool_provenance` 可互相冲刷

**【等级】** Medium  

**【模块】** Multi-thread / Agent Runtime  

**【问题】**  
- `_agents` 上限 48，FIFO 驱逐（非 LRU）；热 thread 可能被挤出（通常靠 checkpointer 可恢复，有重建成本）  
- `all_agent_tools()` 开头 `clear_tool_provenance()`；并发构建 agent 时 provenance 全局表抖动  
- HITL resume 强制 `pop` 重建 agent（正确但掩盖了「interrupt_on 配置应无状态」本应不需要）

**【原因】**  
进程内缓存与全局 registry 未按 thread 分片。

**【推荐修复】**  
LRU；provenance 挂在 agent 实例或不可变快照；构建时 copy-on-write。

**【是否属于架构问题】** 部分（可演进）  

**【是否可能未来再次出现】** 是（100 万用户必现）

---

### AR-13 · Streaming：interrupt chunk 丢弃；overview 仅 done 完整

**【等级】** Medium  

**【模块】** Streaming  

**【问题】**  
`_iter_agent_sse` 遇到 `__interrupt__` 直接 `continue`，最终靠 `get_state` 补发。`overview` 在 `_build_record` 尾部生成，done 前前端可能为空。`final_messages.extend` 在 updates 模式可能重复累计同一消息（依赖 reducer/序列化形态）。

**【原因】**  
SSE 是「尽力推送 + 尾帧权威」，未做事件序号 / 因果序。

**【影响】**  
乱序感知、重复 tool_start、刷新前后 UI 不一致（多数已用前端缓解，协议层仍弱）。

**【推荐修复】**  
事件加 `seq` + `run_id`；interrupt 立即推送；incremental overview 或明确「done 前 overview 可选」。

**【是否属于架构问题】** 部分  

**【是否可能未来再次出现】** 是

---

### AR-14 · Context / Artifact 无限增长风险

**【等级】** Medium  

**【模块】** Context / Workspace  

**【问题】**  
Checkpoint 消息只增不减；Workspace 产物可无限 append；无 summarization / TTL / 配额。Memory `AGENTS.md` 亦可无限追加（且全局）。

**【原因】**  
缺 Context Budget 策略。

**【影响】**  
长 thread 成本爆炸、注意力稀释、串线加剧。

**【推荐修复】**  
消息摘要中间件；Workspace 配额；Memory 条数上限；offload 后从 checkpoint 修剪工具大结果。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-15 · `check_action_permission` 可跳过（策略非强制）

**【等级】** Medium  

**【模块】** HITL / Tool / Prompt  

**【问题】**  
策略检查是可选 Tool；`interrupt_on` 不依赖其返回值。Agent 可直接调写工具。

**【原因】**  
Policy 未升为 Middleware。

**【推荐修复】**  
写工具 `before_call` 强制查 policy；或 interrupt_on 内嵌 policy gate。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-16 · `when` 守卫用「业务终态」近似「已审批」——语义耦合

**【等级】** Medium  

**【模块】** HITL / Lifecycle  

**【问题】**  
`_needs_password_reset`：`status == active` → 不中断。但 `active` 也可能是初始状态或非本审批导致。  
`_needs_license_change`：license 已是目标类型 → 跳过。无法区分「本次审批已应用」与「本来就是该状态」。

**【原因】**  
用领域状态代替 `approval_id` / `applied_actions` 表。

**【影响】**  
误跳过审批；或错误地 already_applied；审计叙事不完整。

**【推荐修复】**  
独立 `applied_actions(tool, args_hash, thread_id, approval_id)`；`when` 查该表。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-17 · 企业级能力缺口：Retry / Rollback / Tracing / Metrics 产品化

**【等级】** Medium（整体）/ 分项 Low–High  

**【模块】** Enterprise  

**【问题】**  

| 能力 | 现状 |
|---|---|
| Exactly Once | 部分（HITL respond）；无通用框架 |
| Audit | 有表，关联弱 |
| Recover | Checkpoint 可恢复对话；无补偿事务 |
| Retry | `http_retry` 仅 RAG/MCP |
| Rollback | 无 |
| Observability | workspace metrics + eval；无 OTel |
| Metrics | 评测向，非生产 SLA |
| Tracing | JSON trace，非分布式 |

**【推荐修复】**  
定义 `WriteUnitOfWork(approval_id)`：Apply → Audit → Checkpoint notice；失败补偿；OTel span 贯穿 API→Graph→Tool。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-18 · Double Write Detection 小结

**【等级】** Critical（协议层） / 当前运行时 High  

**【模块】** Double Write / Single Executor  

**【问题】**  
当前 **业务 DB 双写在主路径上被避免**（Tool Intent + `apply_approved_writes` + `respond`）。但仍存在：

| 模式 | 状态 |
|---|---|
| Tool Apply + HITL Apply | 当前未发生（脆弱，见 AR-04） |
| Main + SubAgent 双发 Intent | 可能（AR-03） |
| Audit 双记 | 是（可接受若语义区分） |
| create_ticket 多入口 | 是（AR-05） |
| approve fallback 再跑 Tool | 是（Intent 再执行，非 DB 双写） |

**【推荐修复】**  
单一执行者清单（见 §3）；CI 断言 `WRITE_TOOLS` 函数体不含 `apply_` / `commit` / `update_ticket(...allow_terminal`）。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是

---

### AR-19 · Single Responsibility：API 层身兼审批编排 + 落库 + SSE + Agent 缓存

**【等级】** Medium  

**【模块】** Agent Runtime / HITL  

**【问题】**  
`api/tasks.py` 同时：缓存 Agent、SSE 协议、HITL prepare/apply、transcript 注入、overview 构建。`hitl_apply` 尚可，但 Runtime 边界模糊。

**【推荐修复】**  
抽出 `HitlRuntime.prepare_resume()` / `AgentSession` / `SseAdapter`；API 只做 HTTP。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是（加功能时文件继续膨胀）

---

### AR-20 · 可扩展性：10 Tool / 100 Skill / 20 SubAgent / 100 万用户

**【等级】** High（面向未来）  

**【模块】** Scalability  

**【问题】**  
- 全量 Tool 注入 Main（+ Sub 重复）→ 上下文与工具选择崩溃  
- Skills 靠目录扫描，无版本/租户  
- SubAgent 硬编码 3 个  
- Agent 进程内 dict 缓存，单机 48  
- SQLite checkpoint + 企业 DB 同机  
- 无租户 / 无队列 / 无水平扩展会话粘滞以外的方案  

**【推荐修复】**  
Tool Registry + 按 Skill 动态挂载；SubAgent 目录化；Checkpoint 外置 Postgres；Agent 无状态 + 外部 checkpointer；租户级 Memory/Workspace。

**【是否属于架构问题】** 是  

**【是否可能未来再次出现】** 是（扩展时必重构）

---

## 2. 检查项对照表（①–⑰）

| # | 检查项 | 结论 | 关键 AR |
|---|---|---|---|
| 1 | Lifecycle 一致性 | 主路径 `respond` 良好；`approve` fallback / 删 thread / 双 Intent 有风险 | AR-04,08,16 |
| 2 | State SoT | 五套存储，Memory/DB 越界 | AR-01,09 |
| 3 | Idempotency | HITL 写部分；create/apply 不足 | AR-05,06 |
| 4 | Context | Workspace 意图清晰；Memory/Context 混用 | AR-01,14 |
| 5 | Agent Runtime | Sub 持写工具；Main 可绕过委派 | AR-03,10 |
| 6 | Workspace | 目录 per-thread；Backend 未强制 | AR-02,07 |
| 7 | Memory | 非真正 LTM 作用域 | AR-01 |
| 8 | HITL | 主路径正确；fallback/重复审批边缘 | AR-04,15,16 |
| 9 | Tool | Intent 模式好；schema/副作用不齐 | AR-05,18 |
| 10 | Prompt | 过度依赖 | AR-10 |
| 11 | Streaming | 可用；序/overview 弱 | AR-13 |
| 12 | 多线程 | Workspace OK；Memory/Sandbox/DB 否 | AR-01,07,12 |
| 13 | Filesystem | 伪 Virtual | AR-02 |
| 14 | 可扩展性 | 百万用户需重构 | AR-20 |
| 15 | 企业级 | Exactly Once/Audit/Recover 不完整 | AR-17 |
| 16 | Double Write | 主路径避免；协议未锁死 | AR-04,18 |
| 17 | SRP | tasks.py / SubAgent 工具包过重 | AR-03,19 |

---

## 3. 目标架构契约（修复必须遵守）

```text
┌─────────────┐     intent only      ┌──────────────┐
│  Write Tool │ ──────────────────► │  interrupt   │
└─────────────┘                      └──────┬───────┘
                                            │ approve
                                            ▼
                                   ┌──────────────────┐
                                   │ apply_approved_* │  ←── Single Executor
                                   │ + idempotency    │
                                   └────────┬─────────┘
                                            │ respond(result)
                                            ▼
                                   ┌──────────────────┐
                                   │ Checkpoint       │
                                   │ (no re-exec)     │
                                   └──────────────────┘

禁止：Tool 内 apply_*
禁止：resume type=approve（写工具）
禁止：SubAgent 挂载 WRITE_TOOLS
禁止：全局可写 Memory / 整仓 Backend root
```

**状态归属**：

| 类型 | 归属 |
|---|---|
| 消息 / todos / 中断点 | Checkpoint |
| 排障产物 / offload | Workspace（per-thread） |
| 组织事实 | Memory org（只读） |
| 账号 / 工单业务态 | Enterprise DB（仅 Apply） |
| 审批记录 | Audit + applied_actions |

---

## 4. Top 10 Architecture Debt

| # | 技术债 | 等级 | 建议迭代 |
|---|---|---|---|
| 1 | Memory 全局共享冒充会话记忆 | Critical | R1 |
| 2 | Backend 整仓可写，Workspace 非强制隔离 | Critical | R1 |
| 3 | SubAgent 挂载写工具 | Critical | R1 |
| 4 | `approve` fallback 破坏 Single Executor | Critical | R1 |
| 5 | 写操作无幂等键 / 无 applied_actions | High | R2 |
| 6 | `create_ticket` 非 Intent、非幂等 | High | R2 |
| 7 | Daytona/Hybrid 单例串线 | High | R2 |
| 8 | Prompt 承担机制职责 | High | R2–R3 |
| 9 | 删 thread 与 checkpoint/业务态生命周期不一致 | High | R2 |
| 10 | 无租户级扩展路径（Tool/Skill/SubAgent 注册表） | High | R3 |

---

## 5. 后续处理计划（本 MD 驱动的逐步修复）

> 原则：**先锁契约（防双写/串线），再补幂等，再拆 Runtime，最后可观测性。**  
> 每步可独立 PR；完成一项在本表勾选并回写 `fix.md`。

### R1 — 正确性防火墙（优先）

| ID | 任务 | 对应 AR | 状态 |
|---|---|---|---|
| R1-1 | 禁止 HITL resume `approve`；失败一律 `respond`/`reject` 错误载荷 | AR-04,18 | `[x]` |
| R1-2 | 裁剪 SubAgent 工具：diagnosis 只读；写工具仅 Main | AR-03 | `[x]` |
| R1-3 | CI/单测：`WRITE_TOOLS` 源码禁止 `apply_` / `allow_terminal` | AR-18 | `[x]` |
| R1-4 | Memory：`AGENTS.md` 改为 per-thread 或降级为 Workspace notes | AR-01 | `[x]` |
| R1-5 | CompositeBackend：强制 `/workspace/{tid}` 可写边界 | AR-02 | `[x]` |

### R2 — Exactly Once & 生命周期

| ID | 任务 | 对应 AR | 状态 |
|---|---|---|---|
| R2-1 | `applied_actions` 表 + apply 幂等 | AR-06,16 | `[x]` |
| R2-2 | `create_ticket` 幂等键或 draft→commit | AR-05 | `[x]` |
| R2-3 | `purge_thread` 清理 checkpoint | AR-08 | `[x]` |
| R2-4 | Daytona/sandbox per-thread 或默认关闭共享可写 | AR-07 | `[x]` |
| R2-5 | Audit 注入 thread_id/task_id（contextvars） | AR-11 | `[x]` |

### R3 — Runtime 硬化 & 扩展

| ID | 任务 | 对应 AR | 状态 |
|---|---|---|---|
| R3-1 | `before_tool` middleware（todos / 重复 ask / policy） | AR-10,15 | `[ ]` |
| R3-2 | 抽出 `HitlRuntime` / `AgentSession`，瘦身 `tasks.py` | AR-19 | `[ ]` |
| R3-3 | SSE `seq` + interrupt 即时事件 | AR-13 | `[ ]` |
| R3-4 | Tool/Skill/SubAgent Registry | AR-20 | `[ ]` |
| R3-5 | OTel tracing + WriteUnitOfWork | AR-17 | `[ ]` |

---

## 6. 做得好的地方（避免误伤）

1. **HITL Intent + `apply_approved_writes` + `respond`**：方向正确，接近 Single Executor。  
2. **`interrupt_on` + `when`**：意识到审批环问题并做了工程化解。  
3. **`update_ticket` 拒绝终态**：终态走专用工具，边界清晰。  
4. **`HarnessBuilder` + `RuntimePorts`**：可测可替换，优于巨型 factory。  
5. **Workspace per-thread 目录 + manifest**：产物可观测性有基础。  
6. **ask_user 使用原生 `interrupt`**：符合 LangGraph 生命周期。

---

## 7. Score 拆解

| 维度 | 分 | 说明 |
|---|---|---|
| Deep Agents 对齐 | 6/10 | 有 Skills/SubAgent/FS/Memory/HITL，但隔离与职责未钉死 |
| LangGraph 生命周期 | 6.5/10 | resume/respond 主路径好；fallback/删除/双 Intent 差 |
| HITL 企业级 | 6/10 | 形态对，幂等与唯一执行者未立法 |
| 状态 / SoT | 4/10 | 多真相源 |
| 多租户 / 隔离 | 3.5/10 | Memory/Sandbox/DB |
| 可扩展性 | 4.5/10 | MVP 硬编码 |
| 可观测 / 运营 | 4/10 | 有 JSON，无 Tracing/Rollback |
| **综合** | **5.5/10** | 优秀 Demo Harness；距生产 Agent Platform 仍有断层 |

---

## 8. 下一步

R1 / R2 已落地。下一迭代按 **R3-1 → R3-2 → R3-3 → R3-4 → R3-5** 推进 Runtime 硬化。  
每完成一项：更新本文件勾选 + 补充回归测试 + 必要时同步 `fix.md`。

**本审查结论一句话**：  
> 业务写路径的「形状」是对的，但 **隔离、幂等、唯一执行者、Backend 强制边界** 尚未成为不可绕过的 Runtime 不变量——这些才是企业 Agent Framework 的真正门槛。
