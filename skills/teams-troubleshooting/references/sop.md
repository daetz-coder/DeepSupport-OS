# Teams 排查 SOP（L2）

工具名必须与仓库 Mock MCP / 远程 MCP 对齐。

## 步骤

1. **身份**：`get_employee(email=…)`，记录部门与经理（升级时用）。
2. **账号**：`get_account_status`、`get_license` —— 无 Teams / M365 许可证则开票换许可（`check_action_permission("license_change")` → `request_license_change`，HITL）。
3. **设备**：`list_user_devices` —— 记录 OS、Office/Teams 客户端版本；写入 `workspace/{thread}/diagnosis.md`。
4. **知识**：`search_docs("Teams 音视频")` / `search_cases`；长文只落盘，消息里留路径。
5. **自助建议**（基于工具结果，勿臆造）：网络、外围设备、经典 Teams vs 新 Teams、防火墙。
6. **工单**：仍失败 → `create_ticket(category="Teams", …)`；复杂升级 → `escalate_ticket`（HITL）。
7. **收尾**：`final_resolution.md`；必要时更新 `/memory/AGENTS.md` 会话记忆（脱敏）。

## 子代理

- 环境深挖 → `task(subagent_type="environment-diagnosis")`
- 文档深挖 → `task(subagent_type="knowledge-research")`
- 开单 → `task(subagent_type="ticket-operations")`
