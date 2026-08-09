"""Tool name → provenance tags (local mock / knowledge / remote MCP)."""

from __future__ import annotations

import threading
from typing import Any

# name -> {"source": "local"|"knowledge"|"remote", "server": str|None}
_REGISTRY: dict[str, dict[str, Any]] = {}
# Lock around every registry op: parallel agent builds (each tool list is tagged
# at build time) otherwise race reads/writes of the shared module-level dict.
_lock = threading.RLock()


def clear_tool_provenance() -> None:
    with _lock:
        _REGISTRY.clear()


def register_tool_provenance(
    name: str,
    *,
    source: str,
    server: str | None = None,
) -> None:
    if not name:
        return
    with _lock:
        _REGISTRY[name] = {"source": source, "server": server}


def tag_tool(tool: Any, *, source: str, server: str | None = None) -> Any:
    """Attach provenance on the tool object and registry."""
    name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
    if name:
        register_tool_provenance(str(name), source=source, server=server)
        try:
            setattr(tool, "_ds_source", source)
            setattr(tool, "_ds_server", server)
        except Exception:  # noqa: BLE001
            pass
    return tool


def lookup_tool_provenance(name: str | None) -> dict[str, Any]:
    if not name:
        return {"source": "unknown", "server": None}
    with _lock:
        hit = _REGISTRY.get(name)
    if hit:
        return dict(hit)
    # Heuristic fallbacks when registry not yet warmed
    if name in {"search_docs", "search_cases", "search_knowledge"}:
        return {"source": "knowledge", "server": None}
    if name in {"read_file", "write_file", "edit_file", "ls", "glob", "grep", "execute", "task"}:
        return {"source": "filesystem", "server": None}
    if name == "ask_user":
        return {"source": "dialogue", "server": None}
    if name == "run_sandbox_shell":
        return {"source": "sandbox", "server": None}
    return {"source": "local", "server": None}


def provenance_snapshot() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _REGISTRY.items()}
