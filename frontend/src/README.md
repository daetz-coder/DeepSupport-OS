# `frontend/src/`

控制台应用源码根。单页：`App.vue` 承载聊天主界面与侧栏管理页。

| 文件 | 作用 |
|------|------|
| `main.ts` | 创建 Vue 应用，挂载 Element Plus 与全局样式 |
| `App.vue` | 主 UI：对话/SSE、HITL 审批、ask_user、线程列表、产物/审计、Skills/MCP 面板、overview |
| `types.ts` | 前后端共享形状：Trace、Interrupt、HITL、Overview、Thread、Skill、MCP 等 |
| `style.css` | 设计 token 与全局布局样式（品牌色、侧栏网格等） |

## 子目录

| 目录 | 职责 |
|------|------|
| [`api/`](./api/) | 后端 base URL、鉴权头、JSON 请求辅助 |
| [`components/`](./components/) | 可复用展示组件 |
| [`composables/`](./composables/) | 组合式逻辑：健康检查、Skills/MCP、气泡、overview、布局 |
| [`utils/`](./utils/) | 纯工具（Markdown 渲染等） |

## 主数据流（简）

```text
App.vue
  → POST /api/tasks/stream (SSE)
  → chatBubbles / liveOverview 更新 UI
  → interrupt → HITL approve/reject 或 ask_user 回答
  → /api/tasks/resume/stream
```
