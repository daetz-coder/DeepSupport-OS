---
name: account-access
description: 账号登录失败、密码、MFA 与锁定问题。当用户无法登录 Microsoft 365 或需要重置密码时使用。
---

# Account Access Skill

1. 确认邮箱
2. `get_account_status` / `get_license` / `get_employee`
3. `check_action_permission("password_reset")`
4. 需要重置时调用 `request_password_reset` 并等待人工审批
5. 审批通过后通知用户，必要时 `create_ticket`
