# Office 应用 SOP（L2）

1. **许可**：`get_license` —— 无 Microsoft 365 Apps / Office 许可则走许可变更 HITL。
2. **设备与版本**：`list_user_devices`。
3. **知识检索**：激活错误码、安全模式、禁用 COM 加载项等文档。
4. **文档损坏**：建议「打开并修复」；勿在未授权情况下改用户文档内容。
5. **公开 Skill 扩展**：若已 `import` docx 相关公开 skill（见 `skills/catalog.json`），可在生成排障报告/附件时按该 skill 的 L2/L3 指引使用；注意其 LICENSE。
6. **工单 / 报告**：`create_ticket` + `final_resolution.md`。
