"""Layered memory files for Deep Agents MemoryMiddleware.

Org facts are shared; session notes are per-thread to avoid cross-talk.
"""

from __future__ import annotations

from pathlib import Path

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.workspace import sanitize_thread_id

# Virtual paths (CompositeBackend routes /memory/ → physical memory/)
ORG_MEMORY_FILE = "/memory/org.md"
# Org-only constant; prefer memory_paths_for_thread(thread_id) at runtime.
MEMORY_PATHS = (ORG_MEMORY_FILE,)

_ORG_TEMPLATE = """# Organization Memory

Stable tenant / demo facts. This file is READ-ONLY for the agent; append
session notes to the thread's AGENTS.md (`/memory/threads/{tid}/AGENTS.md`).

## Contoso (demo)

- Tenant: Contoso Microsoft 365
- Outlook demo: wei.zhang@contoso.com (often locked)
- Teams: na.li@contoso.com
- OneDrive: qiang.wang@contoso.com
- Office activation: min.zhao@contoso.com

## Conventions

- Do not store passwords or tokens here.
"""

_SESSION_TEMPLATE = """# Session Memory

Short, desensitized notes for **this thread only**.
Keep org facts in `/memory/org.md`.

## Notes

（下方由 Agent 追加短条目）
"""


def session_memory_virtual(thread_id: str) -> str:
    """Virtual path for per-thread session memory."""
    tid = sanitize_thread_id(thread_id)
    return f"/memory/threads/{tid}/AGENTS.md"


def memory_paths_for_thread(thread_id: str | None = None) -> list[str]:
    """Paths passed to create_deep_agent(memory=...)."""
    if not thread_id:
        return [ORG_MEMORY_FILE]
    return [ORG_MEMORY_FILE, session_memory_virtual(thread_id)]


def ensure_memory_files(thread_id: str | None = None) -> list[Path]:
    """Ensure org (+ optional per-thread session) files exist; return local paths."""
    settings = get_settings()
    root = settings.resolve("memory")
    root.mkdir(parents=True, exist_ok=True)
    org = root / "org.md"
    if not org.exists():
        org.write_text(_ORG_TEMPLATE, encoding="utf-8")
    out = [org]
    if thread_id:
        tid = sanitize_thread_id(thread_id)
        session_dir = root / "threads" / tid
        session_dir.mkdir(parents=True, exist_ok=True)
        session = session_dir / "AGENTS.md"
        if not session.exists():
            session.write_text(_SESSION_TEMPLATE, encoding="utf-8")
        out.append(session)
    return out


def ensure_memory_file(thread_id: str | None = None) -> Path:
    """Backward-compatible: ensure files, return session path or org."""
    paths = ensure_memory_files(thread_id=thread_id)
    return paths[-1]
