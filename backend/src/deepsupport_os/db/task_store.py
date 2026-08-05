"""SQLite-backed task/thread registry (survives process restart)."""

from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy import desc, select

from deepsupport_os.db.models import TaskRecord, get_session_factory, init_db

_lock = threading.RLock()


def save_task(record: dict[str, Any]) -> None:
    init_db()
    task_id = record["task_id"]
    thread_id = record["thread_id"]
    status = record.get("status", "unknown")
    payload = json.dumps(record, ensure_ascii=False, default=str)
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            row = s.get(TaskRecord, task_id)
            if row is None:
                row = TaskRecord(
                    task_id=task_id,
                    thread_id=thread_id,
                    status=status,
                    payload_json=payload,
                )
                s.add(row)
            else:
                row.thread_id = thread_id
                row.status = status
                row.payload_json = payload
            s.commit()


def get_task(task_id: str) -> dict[str, Any] | None:
    init_db()
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            row = s.get(TaskRecord, task_id)
            if not row:
                return None
            try:
                return json.loads(row.payload_json)
            except json.JSONDecodeError:
                return {
                    "task_id": row.task_id,
                    "thread_id": row.thread_id,
                    "status": row.status,
                }


def get_by_thread(thread_id: str) -> dict[str, Any] | None:
    init_db()
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            row = s.scalar(
                select(TaskRecord)
                .where(TaskRecord.thread_id == thread_id)
                .order_by(desc(TaskRecord.updated_at))
                .limit(1)
            )
            if not row:
                return None
            try:
                return json.loads(row.payload_json)
            except json.JSONDecodeError:
                return {
                    "task_id": row.task_id,
                    "thread_id": row.thread_id,
                    "status": row.status,
                }


def _preview_from_messages(messages: list[Any] | None) -> str:
    """Prefer first user utterance so sidebar titles stay stable across runs."""
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").lower()
        if role in {"user", "human"}:
            content = str(m.get("content") or "").strip()
            if content:
                return content[:120]
    # Fallback: last non-empty content
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        content = str(m.get("content") or "").strip()
        if content:
            return content[:120]
    return ""


def delete_thread(thread_id: str) -> int:
    """Delete all task rows for a conversation thread. Returns deleted count."""
    init_db()
    tid = (thread_id or "").strip()
    if not tid:
        return 0
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            rows = list(
                s.scalars(select(TaskRecord).where(TaskRecord.thread_id == tid)).all()
            )
            for row in rows:
                s.delete(row)
            s.commit()
            return len(rows)


def count_thread_runs(thread_id: str) -> int:
    init_db()
    tid = (thread_id or "").strip()
    if not tid:
        return 0
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            rows = s.scalars(select(TaskRecord).where(TaskRecord.thread_id == tid)).all()
            return len(list(rows))


def sum_thread_duration_ms(thread_id: str, *, exclude_task_id: str | None = None) -> float:
    """Sum metrics.duration_ms across persisted runs for a thread."""
    init_db()
    tid = (thread_id or "").strip()
    if not tid:
        return 0.0
    total = 0.0
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            rows = s.scalars(select(TaskRecord).where(TaskRecord.thread_id == tid)).all()
            for row in rows:
                if exclude_task_id and row.task_id == exclude_task_id:
                    continue
                try:
                    payload = json.loads(row.payload_json)
                except json.JSONDecodeError:
                    continue
                metrics = payload.get("metrics") if isinstance(payload, dict) else None
                if isinstance(metrics, dict) and metrics.get("duration_ms") is not None:
                    try:
                        total += float(metrics["duration_ms"])
                    except (TypeError, ValueError):
                        pass
    return total


def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with _lock:
        Session = get_session_factory()
        with Session() as s:
            rows = s.scalars(
                select(TaskRecord).order_by(desc(TaskRecord.updated_at)).limit(limit)
            ).all()
            out: list[dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(row.payload_json)
                except json.JSONDecodeError:
                    payload = {}
                msgs = payload.get("messages") if isinstance(payload, dict) else None
                out.append(
                    {
                        "task_id": row.task_id,
                        "thread_id": row.thread_id,
                        "status": row.status,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        "preview": _preview_from_messages(msgs if isinstance(msgs, list) else None),
                    }
                )
            return out


def list_threads(limit: int = 40) -> list[dict[str, Any]]:
    """Aggregate runs by thread_id for conversation sidebar (one row per thread)."""
    tasks = list_tasks(limit=max(limit * 4, 80))
    by_thread: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for t in tasks:
        tid = t["thread_id"]
        if tid not in by_thread:
            by_thread[tid] = {
                "thread_id": tid,
                "run_count": 0,
                "latest_status": t["status"],
                "updated_at": t.get("updated_at"),
                "preview": t.get("preview") or "",
                "latest_task_id": t["task_id"],
                "runs": [],
            }
            order.append(tid)
        bucket = by_thread[tid]
        bucket["run_count"] += 1
        # tasks are newest-first; keep first-seen as latest, but prefer a user preview if missing
        if not bucket["preview"] and t.get("preview"):
            bucket["preview"] = t["preview"]
        bucket["runs"].append(
            {
                "task_id": t["task_id"],
                "status": t["status"],
                "updated_at": t.get("updated_at"),
                "preview": t.get("preview") or "",
            }
        )
    return [by_thread[tid] for tid in order[:limit]]
