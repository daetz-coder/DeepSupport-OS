# Architecture

DeepSupport OS layers:

1. **UI / API** — Vue3 + FastAPI (`/api/tasks`, SSE `/api/tasks/stream`, HITL `/api/tasks/resume`)
2. **Harness** — `deepagents.create_deep_agent` with Skills, Subagents, Filesystem, Checkpoint, HITL
3. **Tools** — Mock MCP-style LangChain tools over SQLite enterprise data
4. **Knowledge** — HTTP client to RAGLab; local `data/knowledge/*.md` fallback

```text
User → Vue → FastAPI Tasks API
              ↓
         Deep Agents Harness
         ├── Skills (skills/*/SKILL.md)
         ├── Subagents (knowledge / environment / ticket)
         ├── Checkpoint (data/checkpoints.sqlite)
         └── HITL → hitl_apply → SQLite writes
              ↓
    Mock tools + RAGLabClient / local MD
```

Key packages: `deepsupport_os.harness.agent`, `deepsupport_os.mcp.tools`, `deepsupport_os.rag`, `deepsupport_os.db`.
