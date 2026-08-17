# HITL 审批过早触发问题修复报告

## 问题描述

**现象：** 用户输入"你好，我是张伟，邮箱 wei.zhang@contoso.com。今早 Outlook 一直登不进去，提示账号有问题，帮我看看"后，系统**立即**显示"需要人工审批"的 HITL 审批提示。

**预期行为：** 系统应该先进行环境诊断和知识检索，然后提出解决方案，仅在需要执行高风险写操作（如密码重置、许可证变更、关单、升级工单）时才触发 HITL 审批。

## 根本原因

在之前的重构中，创建了 `main_agent_tools()` 函数来过滤主 Agent 的工具集，目的是让主 Agent 将复杂任务委派给子代理。但是，该函数**过滤掉了所有只读查询工具**：

```python
subagent_only_tools = {
    # ❌ 错误：过滤掉了诊断工具
    "get_employee", "get_department", "get_manager",      # 只读查询
    "get_device", "list_user_devices",                     # 只读查询
    "get_account_status", "get_license",                   # 只读查询
    "search_docs", "get_document", "search_cases",         # 只读检索
    ...
}
```

**结果：**
- 主 Agent 没有任何诊断工具可用
- 无法查询员工、账号、设备等状态
- 无法检索知识文档
- Agent 可能直接"猜测"用户需要密码重置，从而触发 HITL 审批

## 修复方案

修改 `main_agent_tools()` 函数，**保留所有只读查询工具**，只过滤**写操作工具**：

```python
def main_agent_tools():
    """Tools available to the main agent.
    
    Main agent keeps:
    - Read-only query tools (for diagnosis)
    - Read-only knowledge retrieval tools
    - Policy checks (check_action_permission)
    - User interaction (ask_user, notify_user)
    - HITL write operations (request_password_reset, request_license_change, close_ticket, escalate_ticket)
    
    Note: Complex multi-step operations can still be delegated to subagents for parallel processing.
    """
    # ✅ 只过滤创建/修改工单的操作（非终态）
    agent_only_tools = {
        "create_ticket", "update_ticket",  # 委派给 ticket-operations 子代理
    }
    
    # ✅ 保留所有只读查询工具
    # - get_employee, get_department, get_manager
    # - get_device, list_user_devices
    # - get_account_status, get_license
    # - search_docs, get_document, search_cases
    # - get_ticket
    # - check_action_permission
    # - notify_user, ask_user
    # - HITL 写操作（request_password_reset, etc.）
```

## 修复后的正常流程

```
1. 用户输入问题
   ↓
2. Agent 调用 write_todos（建立排障计划）
   ↓
3. Agent 调用诊断工具（只读查询）
   - get_employee("wei.zhang@contoso.com")
   - get_account_status("wei.zhang@contoso.com")
   - list_user_devices("wei.zhang@contoso.com")
   ↓
4. Agent 调用知识检索工具（只读检索）
   - search_docs("Outlook 登录失败")
   ↓
5. Agent 分析诊断结果，提出解决方案
   ↓
6a. 如果是简单问题（如配置错误）→ 直接告知用户解决方案（无需审批）
6b. 如果需要高风险操作（如密码重置）→ 调用 check_action_permission → 触发 HITL 审批
```

## 验证步骤

1. 重新构建 Docker 镜像：`docker-compose build --no-cache api`
2. 重启服务：`docker-compose up -d`
3. 在 UI 中输入测试问题："你好，我是张伟，邮箱 wei.zhang@contoso.com。今早 Outlook 一直登不进去，提示账号有问题，帮我看看"
4. **预期结果：**
   - Agent 先调用诊断工具查询账号状态
   - Agent 检索相关知识文档
   - Agent 提出诊断结论和解决方案
   - **仅在需要执行密码重置等高风险操作时**才显示"需要人工审批"

## 关键原则

1. **诊断优先**：Agent 必须先诊断，再决定行动方案
2. **只读工具开放**：主 Agent 应该有能力进行初步诊断，不必事事委派子代理
3. **写操作受控**：高风险写操作（密码重置、许可证变更、关单、升级）必须经过 HITL 审批
4. **子代理并行**：对于复杂的多步骤任务，可以委派给子代理并行处理，但主 Agent 应该有能力进行初步诊断

## 相关文件

- `backend/src/deepsupport_os/mcp/tools.py` - 工具集定义和过滤
- `backend/src/deepsupport_os/harness/builder.py` - Agent 构建和 interrupt_on 配置
- `backend/src/deepsupport_os/harness/guard_middleware.py` - 工具调用守卫
- `backend/src/deepsupport_os/harness/prompts.py` - 系统提示词约束

## 后续优化建议

1. **系统提示词优化**：可以在系统提示词中更明确地约束"必须先诊断，再执行写操作"
2. **中间件增强**：可以在 `guard_middleware.py` 中添加硬性约束，禁止在没有诊断工具调用的情况下执行写操作
3. **子代理使用指南**：在系统提示词中说明何时应该委派子代理（复杂多步骤任务）vs 直接调用工具（简单查询）
