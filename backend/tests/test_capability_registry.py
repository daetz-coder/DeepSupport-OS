"""R3-4: Tool / Skill / SubAgent capability registry."""

from __future__ import annotations

from deepsupport_os.core.config import get_settings
from deepsupport_os.core.extensions import load_extensions, save_extensions
from deepsupport_os.harness.capability_registry import (
    capabilities_snapshot,
    filter_subagents,
    filter_tools,
    is_subagent_enabled,
    is_tool_enabled,
    list_subagents,
    list_tools,
    set_subagent_enabled,
    set_tool_enabled,
)
from deepsupport_os.harness.subagents import build_mvp_subagents


def _iso_ext(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "ws"))
    get_settings.cache_clear()
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    # extensions resolve under project; point config via workspace-relative path
    from deepsupport_os.core import extensions as ext

    monkeypatch.setattr(ext, "extensions_path", lambda: tmp_path / "config" / "extensions.json")
    save_extensions({})
    return tmp_path


def test_catalog_lists_tools_and_subagents(tmp_path, monkeypatch):
    _iso_ext(tmp_path, monkeypatch)
    tools = list_tools()
    names = {t["name"] for t in tools}
    assert "ask_user" in names
    assert "request_password_reset" in names
    assert all("enabled" in t and "risk" in t for t in tools)
    hitl = [t for t in tools if t["name"] == "close_ticket"][0]
    assert hitl["hitl"] is True
    assert hitl["risk"] == "hitl_write"

    subs = list_subagents()
    assert {s["name"] for s in subs} == {
        "knowledge-research",
        "environment-diagnosis",
        "ticket-operations",
    }


def test_disable_tool_filters_agent_tools(tmp_path, monkeypatch):
    _iso_ext(tmp_path, monkeypatch)
    assert is_tool_enabled("ask_user")
    set_tool_enabled("ask_user", False)
    assert not is_tool_enabled("ask_user")
    assert "ask_user" in load_extensions()["disabled_tools"]

    class _T:
        def __init__(self, name):
            self.name = name

    filtered = filter_tools([_T("ask_user"), _T("get_employee")])
    assert [t.name for t in filtered] == ["get_employee"]
    set_tool_enabled("ask_user", True)
    assert is_tool_enabled("ask_user")


def test_disable_subagent_filters_builder(tmp_path, monkeypatch):
    _iso_ext(tmp_path, monkeypatch)
    set_subagent_enabled("ticket-operations", False)
    assert not is_subagent_enabled("ticket-operations")
    built = build_mvp_subagents()
    assert "ticket-operations" not in {s["name"] for s in built}
    assert len(built) == 2
    set_subagent_enabled("ticket-operations", True)
    assert len(build_mvp_subagents()) == 3


def test_filter_subagents_helper():
    specs = [{"name": "a"}, {"name": "b"}]
    # without extensions isolation, disabled set is empty → pass-through
    assert len(filter_subagents(specs)) == 2


def test_capabilities_snapshot_shape(tmp_path, monkeypatch):
    _iso_ext(tmp_path, monkeypatch)
    snap = capabilities_snapshot()
    assert "tools" in snap and "subagents" in snap and "skills" in snap
    assert isinstance(snap["disabled_tools"], list)
