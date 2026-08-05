"""SSE framing helpers and compact done payload."""

from __future__ import annotations

from deepsupport_os.api.tasks import _slim_interrupt, _sse_done_payload


def test_slim_interrupt_truncates_pregel_tasks():
    huge = "PregelTask(" + ("x" * 500) + ")"
    out = _slim_interrupt(
        {
            "type": "ask",
            "question": "邮箱？",
            "tasks": [huge, "ok"],
        }
    )
    assert out["type"] == "ask"
    assert len(out["tasks"]) == 2
    assert len(out["tasks"][0]) <= 120


def test_sse_done_payload_drops_audit_and_caps_content():
    record = {
        "task_id": "t1",
        "thread_id": "th1",
        "status": "interrupted",
        "workspace_path": "/tmp",
        "messages": [{"role": "human", "content": "hi"}],
        "interrupt": {"type": "ask", "question": "q", "tasks": ["PregelTask(big)"]},
        "todos": [],
        "overview": {
            "status": "interrupted",
            "skills": ["outlook-troubleshooting"],
            "stages": [
                {
                    "id": "plan",
                    "label": "理解与规划",
                    "status": "done",
                    "step_count": 1,
                    "tool_count": 0,
                    "summary": "助手回复",
                    "steps": [{"kind": "assistant", "content": "long" * 100}],
                }
            ],
        },
        "applied_writes": [],
        "artifacts": [],
        "manifest": {"ok": True},
        "metrics": {"duration_ms": 1},
        "memory_paths": [],
        "trace": {
            "steps": [
                {"kind": "tool_result", "name": "read_file", "content": "Z" * 5000},
            ],
            "audit": [{"id": 1, "result": "huge" * 1000}],
            "skills_used": ["outlook-troubleshooting"],
            "stages": [],
        },
    }
    slim = _sse_done_payload(record)
    assert "audit" not in slim.get("trace", {})
    assert len(slim["trace"]["steps"][0]["content"]) < 1300
    assert slim["overview"]["stages"][0].get("steps") is None
    assert slim["interrupt"]["type"] == "ask"
