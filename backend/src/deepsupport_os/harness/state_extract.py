"""Extract Deep Agents / LangGraph state slices for API responses."""

from __future__ import annotations

from typing import Any


def extract_todos(
    agent: Any,
    config: dict,
    result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Read native TodoListMiddleware todos from invoke result or checkpoint state."""
    if isinstance(result, dict):
        todos = result.get("todos")
        if isinstance(todos, list) and todos:
            return _normalize_todos(todos)
    try:
        snap = agent.get_state(config)
        values = getattr(snap, "values", None) or {}
        todos = values.get("todos") or []
        if isinstance(todos, list):
            return _normalize_todos(todos)
    except Exception:  # noqa: BLE001
        pass
    return []


def _normalize_todos(todos: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in todos:
        if isinstance(t, dict):
            content = str(t.get("content") or t.get("task") or "")
            status = str(t.get("status") or "pending")
        else:
            content = str(getattr(t, "content", t))
            status = str(getattr(t, "status", "pending"))
        if not content:
            continue
        if status not in {"pending", "in_progress", "completed"}:
            status = "pending"
        out.append({"content": content, "status": status})
    return out


def extract_memory_paths(settings_memory: list[str] | None) -> list[str]:
    return list(settings_memory or [])
