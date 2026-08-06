# Memory layers

| File | Virtual path | Role | In git? |
|---|---|---|---|
| `org.md` | `/memory/org.md` | Stable org / demo facts (shared) | ✅ committed |
| `threads/{tid}/AGENTS.md` | `/memory/threads/{tid}/AGENTS.md` | Session scratch **per thread** | ❌ ignored |

`create_deep_agent(memory=memory_paths_for_thread(tid))` injects org + that thread’s session file.
Do not put secrets in either file.

Session notes are **thread-scoped** (`harness/memory_files.py`) so concurrent conversations
cannot pollute each other. Stable facts stay in `org.md`.
