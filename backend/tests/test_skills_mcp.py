from deepsupport_os.harness.skills_registry import list_skill_dirs, load_catalog, skill_index, skill_source_paths
from deepsupport_os.mcp.remote_client import build_client_connections, load_mcp_config


def test_skill_sources_and_index():
    roots = skill_source_paths()
    assert roots
    assert all(r.startswith("/") for r in roots)
    assert any(r.rstrip("/").endswith("skills") or "/skills" in r for r in roots)
    dirs = list_skill_dirs()
    names = {d.name for d in dirs}
    assert "outlook-troubleshooting" in names
    assert "teams-troubleshooting" in names
    idx = skill_index()
    assert any(i["name"] == "teams-troubleshooting" and i.get("has_references") for i in idx)
    assert all("enabled" in i for i in idx)


def test_catalog_has_public_entries():
    cat = load_catalog()
    ids = {e["id"] for e in cat.get("entries") or []}
    assert "pdf-anthropic" in ids


def test_mcp_config_example_loads():
    cfg = load_mcp_config()
    assert "servers" in cfg
    assert "employee-remote-http" in cfg["servers"]
    assert cfg["servers"]["employee-remote-http"].get("enabled") is False
    # Disabled by default — enable for connection map smoke
    cfg["servers"]["employee-remote-http"]["enabled"] = True
    conns = build_client_connections(cfg)
    assert "employee-remote-http" in conns
    assert conns["employee-remote-http"]["transport"] in {"streamable_http", "sse", "http"}


def test_skill_toggle_roundtrip(tmp_path, monkeypatch):
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness import skills_registry as reg

    get_settings.cache_clear()
    skills = tmp_path / "skills"
    demo = skills / "demo-skill"
    demo.mkdir(parents=True)
    (demo / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: test\n---\n# Demo\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROOT_DIR", str(tmp_path))  # may not work
    # patch skills_root
    monkeypatch.setattr(reg, "skills_root", lambda: skills)
    item = reg.set_skill_enabled("demo-skill", False)
    assert item["enabled"] is False
    assert (demo / "SKILL.md.off").exists()
    item2 = reg.set_skill_enabled("demo-skill", True)
    assert item2["enabled"] is True
    assert (demo / "SKILL.md").exists()
