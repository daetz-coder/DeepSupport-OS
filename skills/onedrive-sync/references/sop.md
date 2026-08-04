# OneDrive 同步 SOP（L2）

1. **账号与许可**：`get_account_status`、`get_license`（需 OneDrive / SharePoint 相关许可）。
2. **设备**：`list_user_devices` —— 客户端版本、OS；写入 `diagnosis.md`。
3. **知识**：`search_docs("OneDrive 同步")`、`search_cases`；长结果 offload。
4. **处置分支**
   - 账号 locked → 同 Outlook：`check_action_permission` + `request_password_reset`（HITL）
   - 配额/许可 → `request_license_change`（HITL）或工单
   - 客户端问题 → 自助步骤 + 无法解决则 `create_ticket(category="OneDrive")`
5. **收尾**：`final_resolution.md`；可更新 memory 短条目。
