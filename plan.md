# DeepSupport OS — 实施计划（精简）

> Vue3 + FastAPI + Deep Agents · RAGLab HTTP · Mock + **远程 MCP** · Skills 渐进披露 · Daytona sidecar · 不做 CI

**已完成**：0–11 主链路；Teams/OneDrive/Office SOP+references；`skills/catalog` + `import_skill`；远程 MCP client；CONTRIBUTING/SECURITY；online eval 落盘弱断言。

---

## 待办（仅未完成）

### 开源体验（可选）

- [x] `docker compose up` 实测记录补进 README（2026-08-05；并修 ROOT_DIR / `.dockerignore` / compose 宿主机网络）
- [ ] Demo 截图/GIF 填入 `docs/demo-screenshots/`（目录已就绪）

### 评测（后置）

- [ ] Benchmark 扩到 ~100（再后置到 300）

### 明确后置

- 各业务域独立 FastMCP 进程（Employee HTTP 模板已可作远程路径）
- 真实 AD / M365 / ServiceNow / 大规模爬取法务
- CI — **明确不做**

---

## 扩展速查

| 能力 | 入口 |
| --- | --- |
| 前端 Skills / MCP 管理 | UI Tab「Skills」「MCP」 |
| 导入公开 Skill | UI 导入 或 `scripts/import_skill.py` → `skills/imported/` |
| Skills 启停 | 重命名 `SKILL.md` ↔ `SKILL.md.off` · `POST /api/meta/skills/{name}/toggle` |
| Skills 索引 | `GET /api/meta/skills` |
| 远程 MCP 配置 | `config/mcp_servers.json` + UI · `MCP_REMOTE` 经 `config/extensions.json` |
| 远程冒烟 | `employee --http` + `scripts/test_remote_mcp.py` |
| MCP 状态 | `GET /api/meta/mcp` |
