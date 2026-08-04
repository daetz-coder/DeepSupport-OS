# DeepSupport OS — Agent Memory

持久化在 `memory/AGENTS.md`（经 Deep Agents MemoryMiddleware 注入）。
可在对话中用 write_file/edit_file 更新本文件；禁止写入密码、令牌、完整身份证号。

## 组织上下文

- 演示租户：Contoso（Microsoft 365）
- 演示用户：wei.zhang@contoso.com（账号常为 locked，适合 Outlook 登录失败）
- 其他示例：na.li@contoso.com（Teams）、qiang.wang@contoso.com（OneDrive）

## 运行约定

- 长检索/诊断结果写入 `workspace/{thread_id}/`，消息中只保留摘要与路径
- 标准产物文件名：diagnosis.md、retrieved_docs.md、final_resolution.md、ticket_draft.md
- 高风险写操作必须 HITL：密码重置、许可证变更、关闭/升级工单

## 会话记忆（Agent 可追加）

（下方由 Agent 在任务过程中维护简短条目）
