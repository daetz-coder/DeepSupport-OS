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

