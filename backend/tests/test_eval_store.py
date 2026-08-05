"""Eval store: case catalog + run metrics persistence."""

from __future__ import annotations


def test_sync_cases_and_offline_run(fresh_db):
    from deepsupport_os.db import eval_store

    synced = eval_store.sync_eval_cases()
    assert synced["upserted"] >= 20
    cases = eval_store.list_eval_cases()
    assert any(c["id"] == "demo-outlook-login" for c in cases)
    assert "tools" in (cases[0]["expect"] or {}) or cases[0]["expect"] is not None

    # Simulate offline summary like run_eval.py
    results = []
    for c in cases[:5]:
        expect = c.get("expect") or {}
        ok = bool(c.get("id") and c.get("question") and expect and c.get("tags"))
        results.append(
            {
                "id": c["id"],
                "ok": ok,
                "mode": "offline",
                "checks": {
                    "has_id": True,
                    "has_question": True,
                    "has_expect": True,
                    "has_tags": True,
                },
            }
        )
    passed = sum(1 for r in results if r["ok"])
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3),
        "mode": "offline",
        "use_daytona": False,
        "avg_elapsed_ms": None,
        "tool_hit_rate": None,
        "hitl_hit_rate": None,
        "results": results,
    }
    run_id = eval_store.save_eval_run(summary, cases_path="data/benchmark/mvp_cases.jsonl")
    assert run_id

    latest = eval_store.get_latest_eval_run()
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["total"] == 5
    assert latest["pass_rate"] == 1.0
    assert len(latest["results"]) == 5

    runs = eval_store.list_eval_runs(limit=5)
    assert runs and runs[0]["run_id"] == run_id

    metrics = eval_store.metrics_catalog()
    keys = {m["key"] for m in metrics}
    assert "pass_rate" in keys
    assert "tool_hit" in keys
    assert "skill_hit_rate" in keys
    assert "by_tag" in keys
    assert len(metrics) >= 20


def test_eval_api_offline_run(fresh_db):
    from fastapi.testclient import TestClient

    from deepsupport_os.main import create_app

    client = TestClient(create_app())
    sync = client.post("/api/eval/cases/sync")
    assert sync.status_code == 200
    assert sync.json()["upserted"] >= 20

    catalog = client.get("/api/eval/metrics")
    assert catalog.status_code == 200
    assert len(catalog.json()["items"]) >= 5

    cases = client.get("/api/eval/cases")
    assert cases.status_code == 200
    assert len(cases.json()["items"]) >= 20

    run = client.post("/api/eval/run", json={"limit": 3, "from_db": True})
    assert run.status_code == 200
    body = run.json()
    assert body["mode"] == "offline"
    assert body["total"] == 3
    assert body["pass_rate"] == 1.0
    assert body["run_id"]

    latest = client.get("/api/eval/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == body["run_id"]
