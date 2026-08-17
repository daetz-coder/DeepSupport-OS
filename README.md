# DeepSupport OS

Enterprise IT Help Desk Agent Harness：员工报 Outlook / Teams / OneDrive / 激活许可等问题 → Agent 查账号、按 SOP 排障、必要时 HITL 审批写操作。

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

## License

MIT — 见 [LICENSE](LICENSE)。安全披露见 [SECURITY.md](SECURITY.md)。
