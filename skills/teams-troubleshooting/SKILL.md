---
name: teams-troubleshooting
description: Teams 会议、音视频、共享、登录异常排查。当用户提到 Teams 无声音、摄像头、无法入会、共享失败、Teams 登不上时使用。详细步骤见本目录 references/sop.md（渐进披露）。
---

# Teams Troubleshooting

## 何时使用

Teams 会议音视频、共享屏幕、客户端登录失败。

## 渐进披露

1. 本文件：触发与最短路径（始终可被 SkillsMiddleware 按需加载）
2. 详细 SOP：`read_file` → `skills/teams-troubleshooting/references/sop.md`
3. 案例提示：`references/common-causes.md`（仅在仍失败时读取）

## 最短路径

1. 确认邮箱与会议场景 → `get_employee` / `get_account_status` / `get_license`
2. `list_user_devices` → 写入 `diagnosis.md`
3. `search_docs` / `search_cases`（Teams A/V）→ 摘要写入 `retrieved_docs.md`
4. 无法自助解决 → `create_ticket`；结论 → `final_resolution.md`
