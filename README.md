# DeepSupport OS

Enterprise IT Help Desk Agent Harness：员工报 Outlook / Teams / OneDrive / 激活许可等问题 → Agent 查账号、按 SOP 排障、必要时 HITL 审批写操作。

![DeepSupport OS 架构总览](./docs/demo-screenshots/DeepSupport-v2.png)

## 快速开始（Docker）

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY 等
docker compose up --build -d
```

- UI: http://127.0.0.1:5173  
- API: http://127.0.0.1:18000  
- RAGLab UI: http://127.0.0.1:18080  

公网演示（只穿透 UI 端口）：

```powershell
.\scripts\demo-public.ps1
```

## 本地开发

```bash
# API
cd backend && uv sync && uv run uvicorn deepsupport_os.api.main:app --reload --port 8000

# Frontend
cd frontend && npm i && npm run dev
```

可选：`scripts/seed_mock_data.py` 灌 Mock 企业数据；`scripts/ingest_to_raglab.py` 导入 `data/knowledge/`；`scripts/import_skill.py` 导入 Skill。

## 仓库结构

| 路径 | 说明 |
| --- | --- |
| `backend/` | FastAPI + Deep Agents Harness |
| `frontend/` | Vue3 控制台 |
| `skills/` | Builtin SOP Skills |
| `config/` | MCP / extensions |
| `memory/org.md` | 组织级记忆 |
| `data/knowledge/` | 本地知识样例（RAGLab） |
| `docker-compose.yml` | 含 RAGLab 的一键栈 |

## 运行时限流（防烧 Token）

见 `.env.example`：`LLM_MAX_TOKENS`、`AGENT_RECURSION_LIMIT`、`AGENT_MAX_TOOL_CALLS`。

## HITL 与对话守卫（要点）

- **写操作审批**：`create_ticket` / `escalate_ticket` / `close_ticket` / 密码重置 / 许可证变更需人工批准后才落库。
- **工单互斥**：工单已存在时只升级/关闭，勿再 `create_ticket`；同轮出现「升级真实工单 + 创建」时系统只保留升级卡，避免重复 HITL。
- **幂等**：`create_ticket` 按 `title + employee_id` 去重（描述微调不会再次弹审批）。
- **`ask_user`**：首次提问不会被误判为重复；守卫错误 JSON 不会画成用户气泡。
- **时间线**：执行时间线按 task 从 trace 还原，子 agent 工具会嵌套展示。

## License

MIT — 见 [LICENSE](LICENSE)。安全披露见 [SECURITY.md](SECURITY.md)。
