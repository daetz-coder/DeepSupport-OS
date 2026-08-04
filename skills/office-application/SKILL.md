---
name: office-application
description: Word/Excel/PowerPoint 打不开、激活、崩溃与插件冲突排查。当用户提到 Office 无法启动、未授权产品、文档损坏、插件导致崩溃时使用。详细 SOP 见 references/sop.md。
---

# Office Application Skill

## 何时使用

桌面 Office 激活失败、应用崩溃、特定文档打不开。

## 渐进披露

- L2 最短路径：下文
- L3：`references/sop.md`；公开 docx 能力可经 `skills/imported/` 接入（见 catalog）

## 最短路径

1. `get_employee` / `get_account_status` / `get_license`（Office / M365 Apps）
2. `list_user_devices` → Office 版本写入 `diagnosis.md`
3. `search_docs` / `search_cases` → `retrieved_docs.md`
4. 许可问题 → HITL `request_license_change`；否则 `create_ticket(category="Office")`
5. `final_resolution.md`
