# TODO

> 对照 FinalGoal：检查本机能否部署，并经穿透开放到公网。

- [x] 核对根目录 `.env`（对照 `.env.example`）：至少填好 `DEEPSEEK_API_KEY`；确认 `CORS_ORIGINS` 含 `http://localhost:5173` / `http://127.0.0.1:5173`
- [x] 在仓库根执行 `docker compose up --build -d`，确认 `docker-compose.yml` 中 `api`（宿主机 `18000`）与 `frontend`（`5173`）起来；用 `http://127.0.0.1:18000/health` 与 `http://127.0.0.1:5173/` 做本地可达性检查
- [x] compose 纳入 sibling RAGLab（`raglab-qdrant` / `raglab` / `raglab-frontend`）；`api` 使用 `RAGLAB_BASE_URL=http://raglab:8000`；用 `/api/health/deps` 确认 `raglab.ok`
- [x] 修复 RAGLab embedding 模型不可见问题：`models/bge-small-zh-v1.5` 是 NTFS junction，Docker 内解析为悬空符号链接 → 改为真实文件（`model.safetensors` 95MB）
- [x] 本机 UI/API/RAGLab 正常后，在仓库根执行 `powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1`（已起 compose 时可加 `-TunnelMode none` 后手动穿透）；`cloudflared` quick tunnel 成功暴露 `5173` 到公网（实测 `https://bag-tobacco-buy-town.trycloudflare.com`）
- [x] 用公网 URL 验证前端与 SSE 链路（nginx→api→agent→RAGLab→Qdrant 全通，`status → interrupt → done`）；**注意：当前 `.env` 的 `DEEPSEEK_API_KEY`（`****f773`）已被 DeepSeek 判定失效（401）**，agent 的 LLM 调用因此中断 —— 需填入有效 key（`../RAGLab/.env` 同步）或改用本地 Ollama 后重跑对话
