---
name: outlook-troubleshooting
description: Outlook 登录、收发、同步异常的排查 SOP。当用户提到 Outlook 无法登录、凭据错误、同步失败时使用。
---

# Outlook Troubleshooting Skill

## 适用场景

- Outlook 无法登录 / 反复要求输入密码
- 发送接收失败、同步异常

## SOP

1. 确认用户邮箱（UPN）
2. `get_employee` / `get_account_status` / `get_license`
3. `list_user_devices` 收集设备与 Office 版本
4. `search_docs` 检索 Outlook 登录相关文档；长结果写入 `workspace/retrieved_docs.md`
5. `search_cases` 查找相似案例
6. 若账号 locked：`check_action_permission("password_reset")` 后 `request_password_reset`（等待审批）
7. 无法解决：`create_ticket`，把诊断摘要写入工单描述
8. 将最终结论写入 `workspace/final_resolution.md`
