---
name: escalation
description: 无法自动解决或重大故障时的升级与人工转接规则。
---

# Escalation Skill

1. 确认已有工单 `ticket_id`（来自先前 `create_ticket` 批准结果或 `get_ticket`）
2. `check_action_permission("escalate_ticket")`
3. 汇总诊断证据写入 `reason`
4. `escalate_ticket(ticket_id, reason)`（需审批）
   - 工单已存在时**不要**再 `create_ticket`
   - 已 `escalated` 时工具会返回 `already_applied`，勿重复申请 HITL
5. `notify_user` / 通知工程师（Mock）
