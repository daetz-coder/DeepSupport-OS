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
                out.append(
                    {
                        "task_id": row.task_id,
                        "thread_id": row.thread_id,
                        "status": row.status,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        "preview": (payload.get("messages") or [{}])[-1].get("content", "")[:120]
                        if payload.get("messages")
                        else "",
                    }
                )
            return out


def list_threads(limit: int = 40) -> list[dict[str, Any]]:
    """Aggregate runs by thread_id for conversation sidebar."""
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
        bucket["runs"].append(
            {
                "task_id": t["task_id"],
                "status": t["status"],
                "updated_at": t.get("updated_at"),
                "preview": t.get("preview") or "",
            }
        )
    return [by_thread[tid] for tid in order[:limit]]
