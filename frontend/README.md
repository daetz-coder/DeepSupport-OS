# `frontend/`

DeepSupport OS 控制台：Vue 3 + TypeScript + Vite + Element Plus。对接后端 SSE 任务流、HITL / ask_user、Skills / MCP 管理与运行 overview。

## 本层文件

| 文件 | 作用 |
|------|------|
| `index.html` | Vite HTML 入口 |
| `package.json` | 依赖与脚本：`dev` / `build` / `preview` |
| `vite.config.ts` | Vite + Vue 插件配置 |
| `tsconfig*.json` | TS 工程引用（app / node） |
| `README.md` | 本说明（取代默认 Vite 模板文案） |

## 子目录

| 目录 | 职责 |
|------|------|
| [`src/`](./src/) | 应用源码（入口、类型、样式、UI） |
| `dist/` | `vite build` 产物（勿手改） |

## 本地开发

```bash
cd frontend
npm install
npm run dev          # 默认打 VITE_API_BASE→http://127.0.0.1:8000
# 可选 .env：VITE_API_BASE、VITE_ADMIN_TOKEN
```

生产 / Docker：同源经 nginx 代理 `/api` 与 `/health`（见 `api/client.ts`）。
