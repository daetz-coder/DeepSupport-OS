from deepsupport_os.harness.agent import SYSTEM_PROMPT
from deepsupport_os.harness.artifacts import (
    CANONICAL_ARTIFACTS,
    validate_canonical,
    write_manifest,
)
from deepsupport_os.harness.memory_files import (
    MEMORY_PATHS,
    ORG_MEMORY_FILE,
    ensure_memory_files,
)
from deepsupport_os.harness.metrics import summarize_trace, write_turn_metrics
from deepsupport_os.harness.prompts import build_system_prompt
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.harness.workspace import ensure_thread_workspace


def test_system_prompt_is_slim():
    assert "wei.zhang@contoso.com" not in SYSTEM_PROMPT
    assert "工作原则" not in SYSTEM_PROMPT
    assert "硬约束" in SYSTEM_PROMPT
    assert "/memory/org.md" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) < 900


def test_thread_prompt_binds_workspace():
    p = build_system_prompt(thread_id="tid-demo")
    assert "/workspace/tid-demo/" in p
    assert "/memory/threads/tid-demo/AGENTS.md" in p
    assert "manifest.json" in p


def test_memory_layers_seeded():
    paths = ensure_memory_files(thread_id="mem-t1")
    assert len(paths) == 2
    assert paths[0].name == "org.md"
    assert paths[1].name == "AGENTS.md"
    assert "threads" in str(paths[1]).replace("\\", "/")
    assert MEMORY_PATHS == (ORG_MEMORY_FILE,)
    from deepsupport_os.harness.memory_files import memory_paths_for_thread

    injected = memory_paths_for_thread("mem-t1")
    assert ORG_MEMORY_FILE in injected
    assert "/memory/threads/mem-t1/AGENTS.md" in injected
    assert "/memory/AGENTS.md" not in injected
    assert "wei.zhang@contoso.com" in paths[0].read_text(encoding="utf-8")


def test_manifest_and_validation(tmp_path, monkeypatch):
    from deepsupport_os.core.config import get_settings

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    tid = "man-1"
    root = ensure_thread_workspace(tid)
    (root / "diagnosis.md").write_text("locked\n", encoding="utf-8")
    (root / "retrieved_docs.md").write_text("doc\n", encoding="utf-8")
    (root / "final_resolution.md").write_text("done\n", encoding="utf-8")
    body = write_manifest(tid, task_id="t1", status="completed")
    assert body["schema_version"] == 1
    assert (root / "manifest.json").is_file()
    v = validate_canonical(tid)
    assert v["ok"] is True
    assert "ticket_draft.md" in v["missing"]
    get_settings.cache_clear()


def test_metrics_summary_and_write(tmp_path, monkeypatch):
    from deepsupport_os.core.config import get_settings

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    tid = "met-1"
    ensure_thread_workspace(tid)
    trace = {
        "steps": [
            {"kind": "tool_call", "name": "get_employee"},
            {"kind": "tool_result", "content": '{"ok": true}'},
            {"kind": "subagent_dispatch", "name": "knowledge-research"},
        ]
    }
    summary = summarize_trace(trace)
    assert summary["tool_calls"] == 1
    assert summary["subagent_dispatches"] == 1
    body = write_turn_metrics(
        tid, task_id="t2", status="completed", trace=trace, duration_ms=12.5
    )
    assert body["duration_ms"] == 12.5
    get_settings.cache_clear()


def test_subagents_have_output_contract():
    subs = build_mvp_subagents()
    assert len(subs) == 3
    for s in subs:
        assert "输出契约" in s["system_prompt"]
        assert "ERROR:" in s["system_prompt"]


# HITL write tools — must stay Main-only (Single Executor via hitl_apply).
_HITL_WRITE_TOOL_NAMES = frozenset(
    {
        "request_password_reset",
        "request_license_change",
        "close_ticket",
        "escalate_ticket",
    }
)


def test_subagents_do_not_mount_hitl_write_tools():
    """SubAgents must not hold write-intent tools (AR-03 / R1-2)."""
    for sub in build_mvp_subagents():
        names = {getattr(t, "name", None) or getattr(t, "__name__", "") for t in sub["tools"]}
        leaked = names & _HITL_WRITE_TOOL_NAMES
        assert not leaked, f"{sub['name']} mounts HITL write tools: {leaked}"


def test_write_tools_are_intent_only_no_apply_in_source():
    """WRITE tool modules must not call apply_* / allow_terminal (AR-18 / R1-3)."""
    from pathlib import Path

    import deepsupport_os.mcp.tools as tools_mod

    src = Path(tools_mod.__file__).read_text(encoding="utf-8")
    # Strip the read-only helpers / comments by scanning function bodies roughly:
    # forbid apply_* and allow_terminal anywhere in the tools module body.
    assert "apply_password_reset" not in src
    assert "apply_license_change" not in src
    assert "allow_terminal" not in src


def test_thread_backends_isolate_workspace_and_memory(tmp_path, monkeypatch):
    """R1-4 / R1-5: workspace writes and session memory stay per-thread."""
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness.daytona_backend import build_thread_backend, clear_thread_backends
    from deepsupport_os.harness.memory_files import ensure_memory_files, session_memory_virtual

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "ws"))
    get_settings.cache_clear()
    clear_thread_backends()

    b1 = build_thread_backend("iso-a", attach_daytona=False)
    b2 = build_thread_backend("iso-b", attach_daytona=False)

    r1 = b1.write("/workspace/iso-a/note.md", "alpha")
    assert r1.error is None
    assert (tmp_path / "ws" / "iso-a" / "note.md").read_text(encoding="utf-8") == "alpha"
    assert not (tmp_path / "ws" / "iso-b" / "note.md").exists()

    ensure_memory_files("iso-a")
    ensure_memory_files("iso-b")
    v1 = session_memory_virtual("iso-a")
    v2 = session_memory_virtual("iso-b")
    b1.write(v1, "# Session Memory\n\n- note from A\n")
    b2.write(v2, "# Session Memory\n\n- note from B\n")
    a_body = str((getattr(b1.read(v1), "file_data", None) or {}).get("content") or "")
    b_body = str((getattr(b2.read(v2), "file_data", None) or {}).get("content") or "")
    assert "note from A" in a_body
    assert "note from B" in b_body
    assert "note from A" not in b_body

    clear_thread_backends()
    get_settings.cache_clear()


def test_canonical_names_stable():
    assert "diagnosis.md" in CANONICAL_ARTIFACTS
    assert "final_resolution.md" in CANONICAL_ARTIFACTS


def test_readonly_backend_blocks_writes_outside_writable_prefixes(tmp_path):
    """R1-5: wrapper blocks write/edit/delete; read works; threads/ stays writable."""
    from deepsupport_os.harness.daytona_backend import ReadOnlyFilesystemBackend

    root = tmp_path / "mem"
    (root / "threads" / "t1").mkdir(parents=True)
    (root / "org.md").write_text("org", encoding="utf-8")
    (root / "threads" / "t1" / "AGENTS.md").write_text("note", encoding="utf-8")
    b = ReadOnlyFilesystemBackend(root, writable_prefixes=("threads/",))
    assert b.read("/org.md").error is None
    assert b.read("/threads/t1/AGENTS.md").error is None
    assert b.write("/org.md", "x").error is not None
    assert b.edit("/org.md", "org", "n").error is not None
    assert b.delete("/org.md").error is not None
    assert b.write("/threads/t1/AGENTS.md", "new").error is None
    assert (root / "threads" / "t1" / "AGENTS.md").read_text(encoding="utf-8") == "new"
    # Fully read-only variant (skills): nothing is writable.
    ro = ReadOnlyFilesystemBackend(root)
    assert ro.write("/SKILL.md", "x").error is not None
    assert ro.read("/org.md").error is None


def test_skills_memory_mounts_reject_writes(tmp_path, monkeypatch):
    """R1-5: /skills/ and /memory/org.md read-only on the composite; workspace writable."""
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness.daytona_backend import build_thread_backend, clear_thread_backends

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "ws"))
    get_settings.cache_clear()
    clear_thread_backends()
    b = build_thread_backend("ro-x", attach_daytona=False)
    assert b.write("/skills/foo/SKILL.md", "x").error is not None
    assert b.write("/memory/org.md", "overwrite").error is not None
    assert b.read("/memory/org.md").error is None
    assert b.write("/workspace/ro-x/n.md", "ok").error is None
    clear_thread_backends()
    get_settings.cache_clear()


def test_sandbox_scope_local_isolates_per_thread(tmp_path, monkeypatch):
    """R2-4: default scope=local mounts /sandbox/ under workspace/{tid}/sandbox/."""
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness.daytona_backend import build_thread_backend, clear_thread_backends

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "ws"))
    monkeypatch.setenv("DAYTONA_SANDBOX_SCOPE", "local")
    get_settings.cache_clear()
    clear_thread_backends()

    b1 = build_thread_backend("sb-a", attach_daytona=True)
    b2 = build_thread_backend("sb-b", attach_daytona=True)
    r1 = b1.write("/sandbox/note.txt", "alpha")
    assert r1.error is None
    assert (tmp_path / "ws" / "sb-a" / "sandbox" / "note.txt").read_text(encoding="utf-8") == "alpha"
    assert not (tmp_path / "ws" / "sb-b" / "sandbox" / "note.txt").exists()
    clear_thread_backends()
    get_settings.cache_clear()
