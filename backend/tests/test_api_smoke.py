from fastapi.testclient import TestClient

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.models import reset_engine
from deepsupport_os.main import create_app


def test_health_and_root(fresh_db):
    # Ensure app uses the temp DB from fresh_db fixture env
    get_settings.cache_clear()
    reset_engine()
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"
    root = client.get("/").json()
    assert root["project"] == "DeepSupport OS"
    assert "llm_configured" in root


def test_list_tasks_emptyish(fresh_db):
    get_settings.cache_clear()
    reset_engine()
    client = TestClient(create_app())
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert "items" in res.json()


def test_audit_endpoint(fresh_db):
    get_settings.cache_clear()
    reset_engine()
    client = TestClient(create_app())
    res = client.get("/api/tasks/meta/audit")
    assert res.status_code == 200
    assert "items" in res.json()


def test_artifacts_endpoint_for_saved_task(fresh_db, tmp_path, monkeypatch):
    from deepsupport_os.db import task_store
    from deepsupport_os.harness.workspace import ensure_thread_workspace

    get_settings.cache_clear()
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    reset_engine()

    tid = "smoke-art"
    ws = ensure_thread_workspace(tid)
    (ws / "diagnosis.md").write_text("locked account\n", encoding="utf-8")
    task_store.save_task(
        {
            "task_id": "t-art-1",
            "thread_id": tid,
            "status": "completed",
            "workspace_path": str(ws),
            "messages": [],
            "interrupt": None,
            "trace": {},
            "applied_writes": [],
            "todos": [],
            "artifacts": [],
        }
    )
    client = TestClient(create_app())
    res = client.get("/api/tasks/t-art-1/artifacts")
    assert res.status_code == 200
    names = [i["name"] for i in res.json()["items"]]
    assert "diagnosis.md" in names
    detail = client.get("/api/tasks/t-art-1/artifacts/diagnosis.md")
    assert detail.status_code == 200
    assert "locked" in detail.json()["content"]
    get_settings.cache_clear()
