"""Thread-scoped local workspace helpers."""

from __future__ import annotations

import re
from pathlib import Path

from deepsupport_os.core.config import get_settings

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_thread_id(thread_id: str) -> str:
    tid = (thread_id or "default").strip() or "default"
    return _SAFE.sub("_", tid)[:80]


def ensure_thread_workspace(thread_id: str) -> Path:
    """Create and return workspace/{thread_id}/ for context offloading observability."""
    settings = get_settings()
    root = settings.resolve(settings.workspace_dir)
    path = root / sanitize_thread_id(thread_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def thread_workspace_virtual(thread_id: str) -> str:
    """Virtual path for Deep Agents read_file/write_file (must start with /)."""
    return f"/workspace/{sanitize_thread_id(thread_id)}"
