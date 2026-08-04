---
name: ticket-management
description: 创建、更新、升级与关闭 IT 工单。当需要提交工单或无法自动解决时使用。
---

# Ticket Management Skill

1. 汇总已有诊断上下文（账号、设备、文档依据）
2. `create_ticket` 填写完整 title/description/category/priority
3. 升级：`check_action_permission("escalate_ticket")` → `escalate_ticket`
4. 关闭：`check_action_permission("close_ticket")` → `close_ticket`（需审批）
