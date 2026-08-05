# Memory layers

| File | Virtual path | Role | In git? |
|---|---|---|---|
| `org.md` | `/memory/org.md` | Stable org / demo facts | ✅ committed |
| `AGENTS.md` | `/memory/AGENTS.md` | Session scratch (agent may append each run) | ❌ ignored |

Both are passed to Deep Agents `memory=[...]`. Do not put secrets in either file.

`AGENTS.md` is **runtime scratch** — the agent appends per-conversation notes, so it is
`.gitignore`d to keep the working tree clean. It is regenerated from a template on
startup (`harness/memory_files.py` → `ensure_memory_files`). Keep stable facts in
`org.md`, which is committed.
