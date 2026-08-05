# Memory layers

| File | Virtual path | Role |
|---|---|---|
| `org.md` | `/memory/org.md` | Stable org / demo facts |
| `AGENTS.md` | `/memory/AGENTS.md` | Session scratch (agent may append) |

Both are passed to Deep Agents `memory=[...]`. Do not put secrets in either file.
