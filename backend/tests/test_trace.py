from deepsupport_os.api.trace import build_trace, serialize_messages


class FakeAI:
    type = "ai"
    content = "需要重置密码"
    tool_calls = [
        {
            "id": "tc1",
            "name": "request_password_reset",
            "args": {"email": "wei.zhang@contoso.com"},
        }
    ]


class FakeTool:
    type = "tool"
    name = "get_account_status"
    content = '{"status":"locked"}'
    tool_call_id = "x"


def test_serialize_and_trace_pending_writes():
    msgs = [FakeAI(), FakeTool()]
    serialized = serialize_messages(msgs)
    assert serialized[0]["tool_calls"][0]["name"] == "request_password_reset"
    trace = build_trace(msgs)
    assert any(s["kind"] == "tool_call" for s in trace["steps"])
    assert trace["pending_writes"][0]["name"] == "request_password_reset"


def test_subagent_dispatch_marked():
    class FakeTaskAI:
        type = "ai"
        content = ""
        tool_calls = [
            {
                "id": "t1",
                "name": "task",
                "args": {"subagent_type": "knowledge-research", "prompt": "查文档"},
            }
        ]

    trace = build_trace([FakeTaskAI()])
    assert any(s["kind"] == "subagent_dispatch" for s in trace["steps"])
    assert trace["subagent_dispatches"][0]["subagent"] == "knowledge-research"


def test_thread_workspace():
    from deepsupport_os.harness.workspace import ensure_thread_workspace, sanitize_thread_id

    assert sanitize_thread_id("ab/../cd") == "ab_.._cd"
    path = ensure_thread_workspace("test-thread-xyz")
    assert path.exists()
    assert path.name == "test-thread-xyz"


def test_preview_pending_writes():
    from deepsupport_os.harness.hitl_apply import preview_pending_write, preview_pending_writes

    one = preview_pending_write(
        "request_password_reset",
        {"email": "wei.zhang@contoso.com"},
    )
    assert one["label"] == "密码重置"
    assert one["highlights"][0]["key"] == "邮箱"
    assert one["highlights"][0]["value"] == "wei.zhang@contoso.com"

    many = preview_pending_writes(
        [
            {"name": "close_ticket", "args": {"ticket_id": "T-1", "resolution": "fixed"}},
            {"name": "request_license_change", "args": {"email": "a@b.com", "new_license_type": "E5"}},
        ]
    )
    assert many[0]["label"] == "关闭工单"
    assert any(h["key"] == "工单 ID" for h in many[0]["highlights"])
    assert many[1]["label"] == "许可证变更"


def test_context_offload_marked():
    class FakeWriteAI:
        type = "ai"
        content = ""
        tool_calls = [
            {
                "id": "w1",
                "name": "write_file",
                "args": {"file_path": "workspace/t1/diagnosis.md", "content": "# diag"},
            }
        ]

    trace = build_trace([FakeWriteAI()])
    assert any(s["kind"] == "context_offload" for s in trace["steps"])
    assert trace["context_offloads"][0]["offload_path"].endswith("diagnosis.md")


def test_artifacts_list_and_read(tmp_path, monkeypatch):
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.harness import artifacts as art
    from deepsupport_os.harness.workspace import ensure_thread_workspace

    get_settings.cache_clear()
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()

    tid = "art-thread-1"
    ws = ensure_thread_workspace(tid)
    (ws / "final_resolution.md").write_text("# done\n", encoding="utf-8")
    items = art.list_artifacts(tid)
    assert any(i["name"] == "final_resolution.md" and i["canonical"] for i in items)
    data = art.read_artifact(tid, "final_resolution.md")
    assert data["ok"] is True
    assert "done" in data["content"]
    get_settings.cache_clear()


def test_extract_todos_normalize():
    from deepsupport_os.harness.state_extract import extract_todos

    class FakeAgent:
        def get_state(self, _config):
            class Snap:
                values = {
                    "todos": [
                        {"content": "查账号", "status": "completed"},
                        {"content": "HITL 重置", "status": "in_progress"},
                    ]
                }

            return Snap()

    todos = extract_todos(FakeAgent(), {"configurable": {"thread_id": "x"}})
    assert todos[0]["status"] == "completed"
    assert todos[1]["content"] == "HITL 重置"

