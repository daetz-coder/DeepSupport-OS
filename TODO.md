# TODO

> 对照 FinalGoal：检查本机能否部署，并经穿透开放到公网。

- [x] 核对根目录 `.env`（对照 `.env.example`）：至少填好 `DEEPSEEK_API_KEY`；确认 `CORS_ORIGINS` 含 `http://localhost:5173` / `http://127.0.0.1:5173`
- [x] 在仓库根执行 `docker compose up --build -d`，确认 `docker-compose.yml` 中 `api`（宿主机 `18000`）与 `frontend`（`5173`）起来；用 `http://127.0.0.1:18000/health` 与 `http://127.0.0.1:5173/` 做本地可达性检查
- [x] 若 compose 失败或 Docker 不可用：按 README 本地起 `backend`（`uv run deepsupport-os`）+ `frontend`（`npm run dev`），或改跑 `scripts\demo-public.ps1 -LocalDev -SkipTunnel` 先验证本机闭环（compose 已成功，跳过 LocalDev 回退）
- [ ] 本机 UI/API 正常后，在仓库根执行 `powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1`（已起 compose 时可加 `-SkipTunnel` 后手动穿透）；确认 `localtunnel`（`deepsupport-os.loca.lt`）或回退 `cloudflared` 能把 `5173` 暴露到公网
- [ ] 用公网 URL 打开前端并跑一条最小对话（如 `docs/demo.md` 中 `wei.zhang@contoso.com` Outlook 场景），确认 SSE/API 同域可用；失败则查 `docker compose logs` 与穿透窗口输出
