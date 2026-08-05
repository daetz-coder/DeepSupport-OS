from fastapi.testclient import TestClient

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.models import reset_engine
from deepsupport_os.main import create_app


def test_health_and_root(fresh_db, monkeypatch):
    # Ensure app uses the temp DB from fresh_db fixture env
    get_settings.cache_clear()
    reset_engine()

    class _FakeRag:
        def health(self):
            return {"ok": False, "error": "unreachable"}

    monkeypatch.setattr(
        "deepsupport_os.rag.client.RAGLabClient",
        lambda *a, **k: _FakeRag(),
    )
    monkeypatch.setattr(
        "deepsupport_os.harness.daytona_backend.probe_sandbox_status",
        lambda: {
            "ok": False,
            "status": "unconfigured",
            "enabled": True,
            "api_key_configured": False,
        },
    )

    client = TestClient(create_app())
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert "llm_configured" in health
    assert health["raglab"]["ok"] is False
    assert health["sandbox"]["ok"] is False
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


def test_meta_skills_and_mcp(fresh_db):
    get_settings.cache_clear()
    reset_engine()
    client = TestClient(create_app())
    skills = client.get("/api/meta/skills")
    assert skills.status_code == 200
    body = skills.json()
    assert "installed" in body
    assert "catalog" in body
    mcp = client.get("/api/meta/mcp")
    assert mcp.status_code == 200
    assert "settings" in mcp.json()
    assert "config_servers" in mcp.json()
