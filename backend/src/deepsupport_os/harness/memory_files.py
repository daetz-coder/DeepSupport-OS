"""Layered memory files for Deep Agents MemoryMiddleware."""

from __future__ import annotations

from pathlib import Path

from deepsupport_os.core.config import get_settings

# Virtual paths (LocalShell root = repo / Docker /app)
ORG_MEMORY_FILE = "/memory/org.md"
SESSION_MEMORY_FILE = "/memory/AGENTS.md"
MEMORY_PATHS = (ORG_MEMORY_FILE, SESSION_MEMORY_FILE)

_ORG_TEMPLATE = """# Organization Memory

Stable tenant / demo facts. Prefer editing this file over session notes.

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

Short, desensitized notes the agent may append during a thread.
Prefer updating this file for per-conversation facts; keep org facts in `/memory/org.md`.

## Notes

（下方由 Agent 追加短条目）
"""


def ensure_memory_files() -> list[Path]:
    """Create org + session memory files if missing; return local paths."""
    settings = get_settings()
    root = settings.resolve("memory")
    root.mkdir(parents=True, exist_ok=True)
    org = root / "org.md"
    session = root / "AGENTS.md"
    if not org.exists():
        org.write_text(_ORG_TEMPLATE, encoding="utf-8")
    if not session.exists():
        session.write_text(_SESSION_TEMPLATE, encoding="utf-8")
    return [org, session]


def ensure_memory_file() -> Path:
    """Backward-compatible alias: ensure layered files, return session path."""
    paths = ensure_memory_files()
    return paths[-1]
