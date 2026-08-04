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
