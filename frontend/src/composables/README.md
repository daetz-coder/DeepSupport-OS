# `frontend/src/composables/`

Vue 组合式函数与纯转换逻辑：状态拉取、布局、把后端 trace 变成 UI 结构。

| 文件 | 作用 |
|------|------|
| `useHealth.ts` | 探测 `/health` 与 `/api/health/deps`（LLM / RAGLab / Sandbox） |
| `useSkills.ts` | Skills 列表、目录导入、启停（`/api/meta/skills`） |
| `useMcp.ts` | 本地/远程 MCP 开关、服务器 CRUD（`/api/meta/mcp`） |
| `useSidebarLayout.ts` | 左右侧栏可拖拽宽度，localStorage 持久化；窄屏降级 |
| `chatBubbles.ts` | 消息/trace → 聊天气泡；识别 `ask_user`、线程短标签 |
| `liveOverview.ts` | 从 trace/todos 构建运行阶段 overview（工具/Skill/知识/FS 等分桶） |
