---
name: onedrive-sync
description: OneDrive 同步、冲突、占位符与配额问题排查。当用户提到 OneDrive 不同步、文件冲突、云图标异常、配额满时使用。详细 SOP 见 references/sop.md。
---

# OneDrive Sync Skill

## 何时使用

同步卡住、冲突副本、Files On-Demand、配额。

## 渐进披露

- L1：本 frontmatter（启动时由 Harness 注入元数据）
- L2：本文件最短路径
- L3：`references/sop.md`、`references/quota-and-conflicts.md`

## 最短路径

1. `get_employee` + `get_account_status` + `get_license`
2. `list_user_devices` → `diagnosis.md`
3. `search_docs` / `search_cases`（OneDrive sync）→ `retrieved_docs.md`
4. 配额/许可证问题 → 策略检查后 HITL 许可变更或开单
5. `final_resolution.md`
