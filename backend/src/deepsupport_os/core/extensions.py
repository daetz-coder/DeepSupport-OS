"""Runtime extension toggles (Skills / MCP) persisted under config/extensions.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepsupport_os.core.config import get_settings

DEFAULTS: dict[str, Any] = {
    "skills_imported_enabled": True,
    "mcp_local_tools": True,
    "mcp_remote_enabled": False,
    "disabled_tools": [],
    "disabled_subagents": [],
}


def extensions_path() -> Path:
    return get_settings().resolve("config/extensions.json")


def load_extensions() -> dict[str, Any]:
    path = extensions_path()
    data = dict(DEFAULTS)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
        except json.JSONDecodeError:
            pass
    return data


def save_extensions(patch: dict[str, Any]) -> dict[str, Any]:
    data = load_extensions()
    for key, default in DEFAULTS.items():
        if key not in patch:
            continue
        if isinstance(default, bool):
            data[key] = bool(patch[key])
        elif isinstance(default, list):
            raw = patch[key]
            if not isinstance(raw, list):
                raise ValueError(f"{key} must be a list")
            data[key] = [str(x) for x in raw]
        else:
            data[key] = patch[key]
    path = extensions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def ext_bool(key: str) -> bool:
    data = load_extensions()
    if key in data:
        return bool(data[key])
    return bool(DEFAULTS.get(key, False))
