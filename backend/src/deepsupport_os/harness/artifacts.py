"""Canonical workspace artifacts, manifest schema, and listing helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deepsupport_os.harness.workspace import ensure_thread_workspace

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"

# Expected offload / report filenames under workspace/{thread_id}/
CANONICAL_ARTIFACTS = (
    "diagnosis.md",
    "retrieved_docs.md",
    "final_resolution.md",
    "ticket_draft.md",
)

ARTIFACT_ROLES: dict[str, str] = {
    "retrieved_docs.md": "检索摘要与来源",
    "diagnosis.md": "环境/账号诊断",
    "ticket_draft.md": "工单草稿（可选）",
    "final_resolution.md": "最终处理报告",
}

OFFLOAD_TOOL_NAMES = frozenset(
    {
        "write_file",
        "edit_file",
    }
)

_SKIP_NAMES = frozenset({MANIFEST_NAME, "metrics.json", "task.json", "trace.json"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_canonical(thread_id: str, *, min_bytes: int = 1) -> dict[str, Any]:
    """Check which canonical artifacts exist and are non-empty."""
    root = ensure_thread_workspace(thread_id)
    present: list[str] = []
    missing: list[str] = []
    empty: list[str] = []
    for name in CANONICAL_ARTIFACTS:
        path = root / name
        if not path.is_file():
            missing.append(name)
            continue
        size = path.stat().st_size
        if size < min_bytes:
            empty.append(name)
        else:
            present.append(name)
    optional = {"ticket_draft.md"}
    required_missing = [n for n in missing if n not in optional]
    return {
        "ok": not required_missing and not empty,
        "present": present,
        "missing": missing,
        "empty": empty,
        "required_missing": required_missing,
    }


def build_manifest(
    thread_id: str,
    *,
    task_id: str | None = None,
    status: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = ensure_thread_workspace(thread_id)
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        name = path.name
        if name in _SKIP_NAMES:
            continue
        files.append(
            {
                "name": name,
                "path": rel,
                "bytes": path.stat().st_size,
                "canonical": name in CANONICAL_ARTIFACTS,
                "role": ARTIFACT_ROLES.get(name),
                "updated_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    validation = validate_canonical(thread_id)
    body: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "thread_id": thread_id,
        "task_id": task_id,
        "status": status,
        "updated_at": _utcnow(),
        "canonical": [
            {"name": n, "role": ARTIFACT_ROLES.get(n, ""), "required": n != "ticket_draft.md"}
            for n in CANONICAL_ARTIFACTS
        ],
        "files": files,
        "validation": validation,
    }
    if extra:
        body["extra"] = extra
    return body


def write_manifest(
    thread_id: str,
    *,
    task_id: str | None = None,
    status: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write/refresh workspace/{tid}/manifest.json and return the payload."""
    root = ensure_thread_workspace(thread_id)
    body = build_manifest(thread_id, task_id=task_id, status=status, extra=extra)
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return body


def read_manifest(thread_id: str) -> dict[str, Any] | None:
    path = ensure_thread_workspace(thread_id) / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


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
