---
name: ticket-management
description: 创建、更新、升级与关闭 IT 工单。当需要提交工单或无法自动解决时使用。
---

# Ticket Management Skill

1. 汇总已有诊断上下文（账号、设备、文档依据）
2. **仅当尚无工单时** `create_ticket`（完整 title/description/category/priority/employee_id）
   - 同一 title+employee 已创建过 → 勿再 create；用返回的 `ticket_id` 继续
   - `create_ticket` 需 HITL 批准后才落库
3. 调整优先级 / 处理人：`update_ticket(ticket_id, priority="P3")`（勿把 P1–P4 写入 status）
4. 升级：`check_action_permission("escalate_ticket")` → `escalate_ticket(ticket_id, reason)`
   - **禁止**在已有 `ticket_id` 时再调 `create_ticket`
   - 不要与 create 同批调用
5. 关闭：`check_action_permission("close_ticket")` → `close_ticket`（需审批）
