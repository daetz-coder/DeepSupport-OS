"""Skills catalog / MCP management for progressive disclosure & remote connectivity."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deepsupport_os.core.extensions import load_extensions, save_extensions
from deepsupport_os.harness.skills_registry import (
    import_catalog_skill,
    load_catalog,
    set_skill_enabled,
    skill_index,
    skill_source_paths,
)
from deepsupport_os.mcp.remote_client import (
    delete_server,
    load_mcp_config,
    load_remote_mcp_tools,
    mcp_status,
    reset_mcp_cache,
    set_server_enabled,
    upsert_server,
)

router = APIRouter(prefix="/meta", tags=["meta"])


def _reset_agent() -> None:
    from deepsupport_os.api import tasks as tasks_api

    tasks_api._agent = None  # noqa: SLF001


@router.get("/skills")
def get_skills_index():
    ext = load_extensions()
    return {
        "sources": skill_source_paths(),
        "installed": skill_index(include_disabled=True),
        "catalog": load_catalog(),
        "settings": {
            "skills_imported_enabled": ext.get("skills_imported_enabled", True),
        },
    }


class SkillToggle(BaseModel):
    enabled: bool


@router.post("/skills/{name}/toggle")
def toggle_skill(name: str, body: SkillToggle):
    try:
        item = set_skill_enabled(name, body.enabled)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _reset_agent()
    return {"ok": True, "skill": item}


class SkillImportBody(BaseModel):
    catalog_id: str
    accept_license: bool = False


@router.post("/skills/import")
def import_skill(body: SkillImportBody):
    try:
        result = import_catalog_skill(body.catalog_id, accept_license=body.accept_license)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"import failed: {exc}") from exc
    _reset_agent()
    return result


class SkillsSettingsBody(BaseModel):
    skills_imported_enabled: bool | None = None


@router.patch("/skills/settings")
def patch_skills_settings(body: SkillsSettingsBody):
    patch = body.model_dump(exclude_none=True)
    data = save_extensions(patch)
    _reset_agent()
    return {"ok": True, "settings": data}


@router.get("/mcp")
def get_mcp_status():
    cfg = load_mcp_config()
    ext = load_extensions()
    status = mcp_status()
    return {
        "settings": {
            "mcp_local_tools": ext.get("mcp_local_tools", True),
            "mcp_remote_enabled": ext.get("mcp_remote_enabled", False),
        },
        "config_servers": {
            name: {
                "enabled": bool(spec.get("enabled")),
                "transport": spec.get("transport"),
                "url": spec.get("url"),
                "command": spec.get("command"),
                "args": spec.get("args"),
                "description": spec.get("description"),
            }
            for name, spec in (cfg.get("servers") or {}).items()
            if isinstance(spec, dict)
        },
        "runtime": status,
        "notes": cfg.get("notes") or [],
    }


class McpSettingsBody(BaseModel):
    mcp_local_tools: bool | None = None
    mcp_remote_enabled: bool | None = None


@router.patch("/mcp/settings")
def patch_mcp_settings(body: McpSettingsBody):
    patch = body.model_dump(exclude_none=True)
    data = save_extensions(patch)
    reset_mcp_cache()
    _reset_agent()
    return {"ok": True, "settings": data}


class McpServerToggle(BaseModel):
    enabled: bool


@router.post("/mcp/servers/{name}/toggle")
def toggle_mcp_server(name: str, body: McpServerToggle):
    try:
        spec = set_server_enabled(name, body.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"server not found: {name}") from exc
    _reset_agent()
    return {"ok": True, "server": name, "spec": spec}


class McpServerUpsert(BaseModel):
    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")
    transport: str = "streamable_http"
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    description: str = ""
    enabled: bool = True


@router.post("/mcp/servers")
def add_or_update_mcp_server(body: McpServerUpsert):
    spec: dict[str, Any] = {
        "transport": body.transport,
        "description": body.description,
        "enabled": body.enabled,
    }
    if body.url:
        spec["url"] = body.url
    if body.command:
        spec["command"] = body.command
    if body.args is not None:
        spec["args"] = body.args
    try:
        saved = upsert_server(body.name, spec)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _reset_agent()
    return {"ok": True, "server": body.name, "spec": saved}


@router.delete("/mcp/servers/{name}")
def remove_mcp_server(name: str):
    try:
        delete_server(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"server not found: {name}") from exc
    _reset_agent()
    return {"ok": True, "deleted": name}


@router.post("/mcp/reload")
def reload_mcp():
    reset_mcp_cache()
    tools = load_remote_mcp_tools(force=True)
    _reset_agent()
    return {"ok": True, "tool_count": len(tools), "runtime": mcp_status()}
