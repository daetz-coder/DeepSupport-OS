"""Unified Tool / Skill / SubAgent capability registry (AR-20 / R3-4).

SoT for capability metadata + enable/disable; build-time filtering for
Main tools and SubAgents. Skills still live on disk via skills_registry.
"""

from __future__ import annotations

from typing import Any

from deepsupport_os.core.extensions import load_extensions, save_extensions
from deepsupport_os.harness.hitl_apply import WRITE_TOOLS

# Static tool catalog — Main Agent mount candidates (not Deep Agents builtins).
TOOL_CATALOG: list[dict[str, Any]] = [
    {"name": "get_employee", "group": "employee", "risk": "read", "affinity_skills": []},
    {"name": "get_department", "group": "employee", "risk": "read", "affinity_skills": []},
    {"name": "get_manager", "group": "employee", "risk": "read", "affinity_skills": []},
    {"name": "get_device", "group": "asset", "risk": "read", "affinity_skills": []},
    {"name": "list_user_devices", "group": "asset", "risk": "read", "affinity_skills": []},
    {"name": "get_account_status", "group": "account", "risk": "read", "affinity_skills": ["account-access"]},
    {"name": "get_license", "group": "account", "risk": "read", "affinity_skills": ["account-access"]},
    {
        "name": "request_password_reset",
        "group": "account",
        "risk": "hitl_write",
        "affinity_skills": ["account-access"],
    },
    {
        "name": "request_license_change",
        "group": "account",
        "risk": "hitl_write",
        "affinity_skills": ["account-access"],
    },
    {"name": "create_ticket", "group": "ticket", "risk": "write", "affinity_skills": ["ticket-management"]},
    {"name": "get_ticket", "group": "ticket", "risk": "read", "affinity_skills": ["ticket-management"]},
    {"name": "update_ticket", "group": "ticket", "risk": "write", "affinity_skills": ["ticket-management"]},
    {
        "name": "escalate_ticket",
        "group": "ticket",
        "risk": "hitl_write",
        "affinity_skills": ["escalation", "ticket-management"],
    },
    {
        "name": "close_ticket",
        "group": "ticket",
        "risk": "hitl_write",
        "affinity_skills": ["ticket-management"],
    },
    {"name": "search_similar_cases", "group": "case", "risk": "read", "affinity_skills": []},
    {"name": "check_action_permission", "group": "policy", "risk": "policy", "affinity_skills": []},
    {"name": "notify_user", "group": "notification", "risk": "write", "affinity_skills": []},
    {"name": "ask_user", "group": "dialogue", "risk": "dialogue", "affinity_skills": []},
    {"name": "search_docs", "group": "knowledge", "risk": "read", "affinity_skills": []},
    {"name": "get_document", "group": "knowledge", "risk": "read", "affinity_skills": []},
    {"name": "search_cases", "group": "knowledge", "risk": "read", "affinity_skills": []},
]

# SubAgent directory (catalog SoT; builders resolve callables).
SUBAGENT_CATALOG: list[dict[str, Any]] = [
    {
        "name": "knowledge-research",
        "description": "检索 Microsoft 365 支持文档与历史案例",
        "tool_names": ["search_docs", "get_document", "search_cases"],
        "default_enabled": True,
    },
    {
        "name": "environment-diagnosis",
        "description": "查询员工、账号、设备与许可证环境",
        "tool_names": [
            "get_employee",
            "get_department",
            "get_manager",
            "get_account_status",
            "get_license",
            "get_device",
            "list_user_devices",
        ],
        "default_enabled": True,
    },
    {
        "name": "ticket-operations",
        "description": "创建/更新工单（非终态）",
        "tool_names": ["create_ticket", "get_ticket", "update_ticket"],
        "default_enabled": True,
    },
]

_TOOL_BY_NAME = {str(t["name"]): t for t in TOOL_CATALOG}
_SUB_BY_NAME = {str(s["name"]): s for s in SUBAGENT_CATALOG}


def _disabled_set(key: str) -> set[str]:
    raw = load_extensions().get(key) or []
    if not isinstance(raw, list):
        return set()
    return {str(x).strip() for x in raw if str(x).strip()}


def enabled_skill_names(*, include_disabled: bool = False) -> set[str]:
    from deepsupport_os.harness.skills_registry import skill_index

    names: set[str] = set()
    for item in skill_index(include_disabled=include_disabled):
        if include_disabled or item.get("enabled", True):
            names.add(str(item.get("name") or item.get("dir_name") or ""))
    names.discard("")
    return names


def is_tool_enabled(name: str) -> bool:
    if name in _disabled_set("disabled_tools"):
        return False
    spec = _TOOL_BY_NAME.get(name)
    if not spec:
        return True  # remote / unknown: allow unless explicitly disabled
    affinity = list(spec.get("affinity_skills") or [])
    if not affinity:
        return True
    enabled = enabled_skill_names()
    # If none of the affinity skills are installed, do not gate (MVP safety).
    installed = enabled_skill_names(include_disabled=True)
    if not any(s in installed for s in affinity):
        return True
    return any(s in enabled for s in affinity)


def is_subagent_enabled(name: str) -> bool:
    if name in _disabled_set("disabled_subagents"):
        return False
    spec = _SUB_BY_NAME.get(name)
    if spec is None:
        return True
    return bool(spec.get("default_enabled", True))


def set_tool_enabled(name: str, enabled: bool) -> dict[str, Any]:
    disabled = _disabled_set("disabled_tools")
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    save_extensions({"disabled_tools": sorted(disabled)})
    return tool_entry(name)


def set_subagent_enabled(name: str, enabled: bool) -> dict[str, Any]:
    if name not in _SUB_BY_NAME:
        raise KeyError(name)
    disabled = _disabled_set("disabled_subagents")
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    save_extensions({"disabled_subagents": sorted(disabled)})
    return subagent_entry(name)


def tool_entry(name: str) -> dict[str, Any]:
    spec = dict(_TOOL_BY_NAME.get(name) or {"name": name, "group": "unknown", "risk": "unknown"})
    spec["enabled"] = is_tool_enabled(name)
    spec["hitl"] = name in WRITE_TOOLS
    return spec


def subagent_entry(name: str) -> dict[str, Any]:
    spec = dict(_SUB_BY_NAME.get(name) or {"name": name})
    spec["enabled"] = is_subagent_enabled(name)
    return spec


def list_tools() -> list[dict[str, Any]]:
    known = [tool_entry(str(t["name"])) for t in TOOL_CATALOG]
    # Include explicitly disabled unknowns so ops can see toggles.
    catalog_names = {str(t["name"]) for t in TOOL_CATALOG}
    for name in sorted(_disabled_set("disabled_tools")):
        if name not in catalog_names:
            known.append(tool_entry(name))
    return known


def list_subagents() -> list[dict[str, Any]]:
    return [subagent_entry(str(s["name"])) for s in SUBAGENT_CATALOG]


def filter_tools(tools: list[Any]) -> list[Any]:
    """Drop tools whose registry name is disabled / skill-gated."""
    out: list[Any] = []
    for t in tools:
        name = str(getattr(t, "name", None) or getattr(t, "__name__", "") or "")
        if name and not is_tool_enabled(name):
            continue
        out.append(t)
    return out


def filter_subagents(subagents: list[dict]) -> list[dict]:
    return [s for s in subagents if is_subagent_enabled(str(s.get("name") or ""))]


def capabilities_snapshot() -> dict[str, Any]:
    from deepsupport_os.harness.skills_registry import skill_index, skill_source_paths

    return {
        "tools": list_tools(),
        "subagents": list_subagents(),
        "skills": {
            "sources": skill_source_paths(),
            "installed": skill_index(include_disabled=True),
        },
        "disabled_tools": sorted(_disabled_set("disabled_tools")),
        "disabled_subagents": sorted(_disabled_set("disabled_subagents")),
    }
