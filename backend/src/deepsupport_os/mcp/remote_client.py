"""Load tools from local and remote MCP servers (MultiServerMCPClient)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)

_cached_tools: list[Any] | None = None
_cached_status: dict[str, Any] | None = None


def mcp_config_path() -> Path:
    settings = get_settings()
    return settings.resolve(settings.mcp_servers_config)


def load_mcp_config() -> dict[str, Any]:
    path = mcp_config_path()
    if not path.exists():
        example = settings_example_path()
        if example.exists():
            return json.loads(example.read_text(encoding="utf-8"))
        return {"servers": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def settings_example_path() -> Path:
    return get_settings().resolve("config/mcp_servers.example.json")


def build_client_connections(cfg: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Filter enabled servers into MultiServerMCPClient connection map."""
    cfg = cfg or load_mcp_config()
    out: dict[str, dict[str, Any]] = {}
    for name, spec in (cfg.get("servers") or {}).items():
        if not isinstance(spec, dict) or not spec.get("enabled", False):
            continue
        transport = str(spec.get("transport") or "stdio")
        entry: dict[str, Any] = {"transport": transport}
        if transport in {"sse", "http", "streamable_http"}:
            url = spec.get("url")
            if not url:
                continue
            entry["url"] = url
            if spec.get("headers"):
                entry["headers"] = spec["headers"]
        else:
            cmd = spec.get("command")
            if not cmd:
                continue
            entry["command"] = cmd
            entry["args"] = list(spec.get("args") or [])
            if spec.get("env"):
                entry["env"] = spec["env"]
            # Local: <repo>/backend; Docker image WORKDIR is already /app
            root = get_settings().root_dir
            backend_dir = root / "backend"
            entry["cwd"] = str(backend_dir if backend_dir.is_dir() else root)
        out[name] = entry
    return out


async def _fetch_tools_async(connections: dict[str, dict[str, Any]]) -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(connections)
    return list(await client.get_tools())


def _run_coro(coro):
    """Run coroutine from sync code even if a loop is already running (FastAPI)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def load_remote_mcp_tools(*, force: bool = False) -> list[Any]:
    """Sync helper: pull tools from enabled MCP servers. Cached after first success."""
    global _cached_tools, _cached_status
    from deepsupport_os.core.extensions import ext_bool

    if not ext_bool("mcp_remote_enabled"):
        _cached_status = {"enabled": False, "servers": {}, "tool_count": 0}
        _cached_tools = []
        return []

    if _cached_tools is not None and not force:
        return _cached_tools

    connections = build_client_connections()
    if not connections:
        _cached_tools = []
        _cached_status = {
            "enabled": True,
            "servers": {},
            "tool_count": 0,
            "warning": "no enabled servers in mcp config",
        }
        return []

    status: dict[str, Any] = {"enabled": True, "servers": {}, "tool_count": 0}
    try:
        tools = _run_coro(_fetch_tools_async(connections))
        _cached_tools = tools
        status["tool_count"] = len(tools)
        status["tool_names"] = [getattr(t, "name", str(t)) for t in tools]
        for name in connections:
            status["servers"][name] = {"ok": True, "transport": connections[name]["transport"]}
        _cached_status = status
        logger.info("Loaded %s remote MCP tools from %s", len(tools), list(connections))
        return tools
    except Exception as exc:  # noqa: BLE001
        logger.warning("Remote MCP load failed: %s", exc)
        _cached_tools = []
        status["error"] = str(exc)
        for name, conn in connections.items():
            status["servers"][name] = {"ok": False, "transport": conn.get("transport"), "error": str(exc)}
        _cached_status = status
        return []


def mcp_status() -> dict[str, Any]:
    if _cached_status is None:
        load_remote_mcp_tools()
    return dict(_cached_status or {"enabled": False})


def reset_mcp_cache() -> None:
    global _cached_tools, _cached_status
    _cached_tools = None
    _cached_status = None


def save_mcp_config(cfg: dict[str, Any]) -> dict[str, Any]:
    path = mcp_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    reset_mcp_cache()
    return cfg


def set_server_enabled(name: str, enabled: bool) -> dict[str, Any]:
    cfg = load_mcp_config()
    servers = cfg.setdefault("servers", {})
    if name not in servers or not isinstance(servers[name], dict):
        raise KeyError(name)
    servers[name]["enabled"] = bool(enabled)
    save_mcp_config(cfg)
    return servers[name]


def upsert_server(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    cfg = load_mcp_config()
    servers = cfg.setdefault("servers", {})
    existing = servers.get(name) if isinstance(servers.get(name), dict) else {}
    merged = {**existing, **spec, "enabled": bool(spec.get("enabled", existing.get("enabled", True)))}
    transport = str(merged.get("transport") or "streamable_http")
    merged["transport"] = transport
    if transport in {"sse", "http", "streamable_http"} and not merged.get("url"):
        raise ValueError("url required for http/sse transports")
    if transport == "stdio" and not merged.get("command"):
        raise ValueError("command required for stdio transport")
    servers[name] = merged
    save_mcp_config(cfg)
    return merged


def delete_server(name: str) -> None:
    cfg = load_mcp_config()
    servers = cfg.get("servers") or {}
    if name not in servers:
        raise KeyError(name)
    del servers[name]
    save_mcp_config(cfg)
