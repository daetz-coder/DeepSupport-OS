"""Persist automated eval cases, runs, and per-case metrics to SQLite."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.models import EvalCase, EvalCaseResult, EvalRun, init_db, get_session_factory

_lock = threading.RLock()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _loads(text: str | None, fallback: Any) -> Any:
    if not text:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def default_cases_path() -> Path:
    settings = get_settings()
    full = settings.resolve("data/benchmark/full_cases.jsonl")
    if full.exists():
        return full
    return settings.resolve("data/benchmark/mvp_cases.jsonl")


def load_cases_from_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or default_cases_path()
    rows: list[dict[str, Any]] = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def sync_eval_cases(
    cases: list[dict[str, Any]] | None = None,
    *,
    source: str = "full_cases",
    path: Path | None = None,
    disable_missing: bool = True,
) -> dict[str, int]:
    """Upsert benchmark cases into eval_cases. Returns {upserted, total, disabled}."""
    with _lock:
        init_db()
        rows = cases if cases is not None else load_cases_from_jsonl(path)
        Session = get_session_factory()
        upserted = 0
        disabled = 0
        keep_ids: set[str] = set()
        with Session() as s:
            for case in rows:
                case_id = str(case.get("id") or "").strip()
                if not case_id:
                    continue
                keep_ids.add(case_id)
                question = str(case.get("question") or "")
                expect = case.get("expect") or {}
                tags = case.get("tags") or []
                existing = s.get(EvalCase, case_id)
                if existing is None:
                    s.add(
                        EvalCase(
                            case_id=case_id,
                            question=question,
                            expect_json=_dumps(expect),
                            tags_json=_dumps(tags),
                            source=source,
                            enabled=True,
                        )
                    )
                else:
                    existing.question = question
                    existing.expect_json = _dumps(expect)
                    existing.tags_json = _dumps(tags)
                    existing.source = source
                    existing.enabled = True
                upserted += 1
            if disable_missing and keep_ids:
                for row in s.scalars(select(EvalCase)).all():
                    if row.case_id not in keep_ids and row.enabled:
                        row.enabled = False
                        disabled += 1
            s.commit()
        return {"upserted": upserted, "total": upserted, "disabled": disabled}


def list_eval_cases(*, enabled_only: bool = True, limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        init_db()
        Session = get_session_factory()
        with Session() as s:
            q = select(EvalCase).order_by(EvalCase.case_id)
            if enabled_only:
                q = q.where(EvalCase.enabled.is_(True))
            q = q.limit(limit)
            out: list[dict[str, Any]] = []
            for row in s.scalars(q).all():
                out.append(
                    {
                        "id": row.case_id,
                        "question": row.question,
                        "expect": _loads(row.expect_json, {}),
                        "tags": _loads(row.tags_json, []),
                        "source": row.source,
                        "enabled": row.enabled,
                    }
                )
            return out


def save_eval_run(
    summary: dict[str, Any],
    *,
    cases_path: str = "",
    run_id: str | None = None,
) -> str:
    """Persist aggregate metrics + per-case results. Returns run_id."""
    with _lock:
        init_db()
        rid = run_id or str(uuid.uuid4())
        results = list(summary.get("results") or [])
        offload_vals = [r.get("offload_hit") for r in results if r.get("offload_hit") is not None]
        offload_rate = None
        if summary.get("mode") == "online" and offload_vals:
            offload_rate = round(sum(1 for v in offload_vals if v) / len(offload_vals), 3)

        Session = get_session_factory()
        with Session() as s:
            s.add(
                EvalRun(
                    run_id=rid,
                    mode=str(summary.get("mode") or "offline"),
                    cases_path=cases_path or "",
                    use_daytona=bool(summary.get("use_daytona")),
                    total=int(summary.get("total") or 0),
                    passed=int(summary.get("passed") or 0),
                    failed=int(summary.get("failed") or 0),
                    pass_rate=summary.get("pass_rate"),
                    avg_elapsed_ms=summary.get("avg_elapsed_ms"),
                    tool_hit_rate=summary.get("tool_hit_rate"),
                    hitl_hit_rate=summary.get("hitl_hit_rate"),
                    offload_hit_rate=offload_rate,
                    summary_json=_dumps({k: v for k, v in summary.items() if k != "results"}),
                )
            )
            for item in results:
                case_id = str(item.get("id") or "unknown")
                s.add(
                    EvalCaseResult(
                        run_id=rid,
                        case_id=case_id,
                        ok=bool(item.get("ok")),
                        mode=str(item.get("mode") or summary.get("mode") or "offline"),
                        elapsed_ms=item.get("elapsed_ms"),
                        tool_hit=item.get("tool_hit"),
                        hitl_hit=item.get("hitl_hit"),
                        offload_hit=item.get("offload_hit"),
                        error=str(item["error"]) if item.get("error") else None,
                        result_json=_dumps(item),
                    )
                )
            s.commit()
        return rid


def get_eval_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        init_db()
        Session = get_session_factory()
        with Session() as s:
            run = s.get(EvalRun, run_id)
            if run is None:
                return None
            results = s.scalars(
                select(EvalCaseResult)
                .where(EvalCaseResult.run_id == run_id)
                .order_by(EvalCaseResult.id)
            ).all()
            return _run_to_dict(run, results)


def list_eval_runs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        init_db()
        Session = get_session_factory()
        with Session() as s:
            rows = s.scalars(
                select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)
            ).all()
            return [_run_to_dict(r, include_results=False) for r in rows]


def get_latest_eval_run() -> dict[str, Any] | None:
    runs = list_eval_runs(limit=1)
    if not runs:
        return None
    return get_eval_run(runs[0]["run_id"])


def metrics_catalog() -> list[dict[str, str]]:
    """Documented metrics stored on eval_runs / eval_case_results."""
    from deepsupport_os.harness.eval_metrics import metrics_catalog as _catalog

    return _catalog()



def _run_to_dict(
    run: EvalRun,
    results: list[EvalCaseResult] | None = None,
    *,
    include_results: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "run_id": run.run_id,
        "mode": run.mode,
        "cases_path": run.cases_path,
        "use_daytona": run.use_daytona,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "pass_rate": run.pass_rate,
        "avg_elapsed_ms": run.avg_elapsed_ms,
        "tool_hit_rate": run.tool_hit_rate,
        "hitl_hit_rate": run.hitl_hit_rate,
        "offload_hit_rate": run.offload_hit_rate,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "summary": _loads(run.summary_json, {}),
    }
    if include_results:
        rows = results
        if rows is None:
            Session = get_session_factory()
            with Session() as s:
                rows = list(
                    s.scalars(
                        select(EvalCaseResult)
                        .where(EvalCaseResult.run_id == run.run_id)
                        .order_by(EvalCaseResult.id)
                    ).all()
                )
        body["results"] = [
            {
                "case_id": r.case_id,
                "ok": r.ok,
                "mode": r.mode,
                "elapsed_ms": r.elapsed_ms,
                "tool_hit": r.tool_hit,
                "hitl_hit": r.hitl_hit,
                "offload_hit": r.offload_hit,
                "error": r.error,
                "detail": _loads(r.result_json, {}),
            }
            for r in rows
        ]
    return body
