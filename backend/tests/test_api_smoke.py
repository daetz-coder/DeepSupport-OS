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
