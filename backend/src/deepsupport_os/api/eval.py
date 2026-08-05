"""Automated eval catalog, runs, and metrics API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from deepsupport_os.db import eval_store

router = APIRouter(prefix="/eval", tags=["eval"])


class SyncCasesBody(BaseModel):
    path: str | None = Field(default=None, description="Optional jsonl path; default mvp_cases.jsonl")


@router.get("/metrics")
def get_metrics_catalog():
    """Documented metrics persisted on eval_runs / eval_case_results."""
    return {"items": eval_store.metrics_catalog()}


@router.get("/cases")
def get_eval_cases(
    enabled_only: bool = Query(True),
    limit: int = Query(200, ge=1, le=500),
):
    return {"items": eval_store.list_eval_cases(enabled_only=enabled_only, limit=limit)}


@router.post("/cases/sync")
def sync_cases(body: SyncCasesBody | None = None):
    """Upsert benchmark cases from jsonl into eval_cases."""
    from pathlib import Path

    path = Path(body.path) if body and body.path else None
    return eval_store.sync_eval_cases(path=path)


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100)):
    return {"items": eval_store.list_eval_runs(limit=limit)}


@router.get("/runs/latest")
def latest_run():
    row = eval_store.get_latest_eval_run()
    if not row:
        raise HTTPException(status_code=404, detail="no eval runs yet")
    return row


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    row = eval_store.get_eval_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="eval run not found")
    return row


class RunEvalBody(BaseModel):
    limit: int = Field(default=0, ge=0, le=100)
    from_db: bool = True


def _score_offline(case: dict[str, Any]) -> dict[str, Any]:
    expect = case.get("expect") or {}
    checks = {
        "has_id": bool(case.get("id")),
        "has_question": bool(case.get("question")),
        "has_expect": bool(expect),
        "has_tags": bool(case.get("tags")),
    }
    ok = all(checks.values())
    return {
        "id": case.get("id"),
        "ok": ok,
        "mode": "offline",
        "checks": checks,
        "expect_keys": sorted(expect.keys()) if isinstance(expect, dict) else [],
    }


@router.post("/run")
def trigger_offline_eval(body: RunEvalBody | None = None) -> dict[str, Any]:
    """Run offline schema eval, sync cases, and persist metrics to SQLite.

    For online LLM eval use: `uv run python ../scripts/run_eval.py --online --limit N`
    """
    body = body or RunEvalBody()
    synced = eval_store.sync_eval_cases()
    if body.from_db:
        cases = eval_store.list_eval_cases(enabled_only=True)
    else:
        cases = eval_store.load_cases_from_jsonl()
    if body.limit:
        cases = cases[: body.limit]

    results = []
    for c in cases:
        row = _score_offline(c)
        row["tags"] = list(c.get("tags") or [])
        results.append(row)

    from deepsupport_os.harness.eval_metrics import aggregate_summary

    summary = aggregate_summary(results, mode="offline", use_daytona=False)
    run_id = eval_store.save_eval_run(
        summary, cases_path=str(eval_store.default_cases_path())
    )
    return {
        "run_id": run_id,
        "synced_cases": synced,
        "total": summary["total"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "pass_rate": summary["pass_rate"],
        "mode": "offline",
        "error_rate": summary.get("error_rate"),
        "by_tag": summary.get("by_tag"),
        "metrics_available": [m["key"] for m in eval_store.metrics_catalog()],
    }
