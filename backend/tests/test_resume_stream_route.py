"""Smoke: resume/stream route is registered."""

from fastapi.testclient import TestClient

from deepsupport_os.main import app


def test_resume_stream_route_exists():
    paths = set(app.openapi()["paths"])
    assert "/api/tasks/resume/stream" in paths
    assert "/api/tasks/stream" in paths


def test_resume_stream_requires_answer(fresh_db):
    client = TestClient(app)
    res = client.post(
        "/api/tasks/resume/stream",
        json={"thread_id": "missing-thread", "interrupt_type": "ask", "answer": ""},
    )
    assert res.status_code == 400
