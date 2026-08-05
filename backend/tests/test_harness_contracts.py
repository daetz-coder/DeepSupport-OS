from deepsupport_os.harness.agent import SYSTEM_PROMPT
from deepsupport_os.harness.artifacts import (
    CANONICAL_ARTIFACTS,
    validate_canonical,
    write_manifest,
)
from deepsupport_os.harness.metrics import summarize_trace, write_turn_metrics
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.harness.workspace import ensure_thread_workspace


def test_system_prompt_is_slim():
    assert "wei.zhang@contoso.com" not in SYSTEM_PROMPT
    assert "工作原则" not in SYSTEM_PROMPT
    assert "硬约束" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) < 900


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


def test_canonical_names_stable():
    assert "diagnosis.md" in CANONICAL_ARTIFACTS
    assert "final_resolution.md" in CANONICAL_ARTIFACTS
