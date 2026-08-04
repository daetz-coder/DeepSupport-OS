"""Canonical workspace artifacts and listing helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deepsupport_os.harness.workspace import ensure_thread_workspace

# Expected offload / report filenames under workspace/{thread_id}/
CANONICAL_ARTIFACTS = (
    "diagnosis.md",
    "retrieved_docs.md",
    "final_resolution.md",
    "ticket_draft.md",
)

OFFLOAD_TOOL_NAMES = frozenset(
    {
        "write_file",
        "edit_file",
    }
)


def list_artifacts(thread_id: str, *, preview_chars: int = 400) -> list[dict[str, Any]]:
    """List files in the thread workspace (artifacts + any offloads)."""
    root = ensure_thread_workspace(thread_id)
    items: list[dict[str, Any]] = []
    if not root.exists():
        return items
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        name = path.name
        items.append(
            {
                "name": name,
                "path": rel,
                "bytes": path.stat().st_size,
                "canonical": name in CANONICAL_ARTIFACTS,
                "updated_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "preview": text[:preview_chars],
            }
        )
    return items


def read_artifact(thread_id: str, relative_path: str) -> dict[str, Any]:
    root = ensure_thread_workspace(thread_id)
    # Prevent path escape
    target = (root / relative_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        return {"ok": False, "error": "invalid_path"}
    if not target.is_file():
        return {"ok": False, "error": "not_found"}
    text = target.read_text(encoding="utf-8", errors="ignore")
    return {
        "ok": True,
        "name": target.name,
        "path": target.relative_to(root).as_posix(),
        "bytes": target.stat().st_size,
        "canonical": target.name in CANONICAL_ARTIFACTS,
        "content": text,
    }
