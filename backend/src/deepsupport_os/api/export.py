"""Data export utilities for DeepSupport OS."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from deepsupport_os.db import task_store

router = APIRouter()


@router.get("/conversations")
async def export_conversations_endpoint(
    thread_ids: str | None = None,
    format: str = "json",
):
    """Export conversation history.
    
    Query params:
        thread_ids: Comma-separated list of thread IDs. If empty, export all.
        format: Export format - "json" or "csv"
    """
    thread_id_list = None
    if thread_ids:
        thread_id_list = [tid.strip() for tid in thread_ids.split(",")]
    
    return export_conversations(thread_id_list, format)


@router.get("/tasks")
async def export_tasks_endpoint(
    task_ids: str | None = None,
    format: str = "json",
):
    """Export task details.
    
    Query params:
        task_ids: Comma-separated list of task IDs. If empty, export recent.
        format: Export format - "json"
    """
    task_id_list = None
    if task_ids:
        task_id_list = [tid.strip() for tid in task_ids.split(",")]
    
    return export_tasks(task_id_list, format)


@router.get("/audit")
async def export_audit_endpoint(
    limit: int = 1000,
    format: str = "json",
):
    """Export audit log.
    
    Query params:
        limit: Maximum number of records
        format: Export format - "json" or "csv"
    """
    return export_audit_log(limit, format)


def export_conversations(
    thread_ids: list[str] | None = None,
    format: str = "json",
) -> StreamingResponse:
    """Export conversation history.
    
    Args:
        thread_ids: List of thread IDs to export. If None, export all.
        format: Export format - "json" or "csv"
    
    Returns:
        StreamingResponse with exported data
    """
    if thread_ids:
        threads = [task_store.get_thread(tid) for tid in thread_ids]
        threads = [t for t in threads if t]
    else:
        threads = task_store.list_threads(limit=1000)
    
    if format == "json":
        # Export as JSON
        data = []
        for thread in threads:
            tasks = task_store.list_tasks_by_thread(thread["thread_id"])
            thread_data = {
                "thread_id": thread["thread_id"],
                "tasks": tasks,
                "task_count": len(tasks),
                "created_at": thread.get("created_at"),
                "updated_at": thread.get("updated_at"),
            }
            data.append(thread_data)
        
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        
        return StreamingResponse(
            io.BytesIO(json_str.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )
    
    elif format == "csv":
        # Export as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "thread_id",
            "task_id",
            "status",
            "created_at",
            "updated_at",
            "message_count",
            "duration_ms",
        ])
        
        # Write data
        for thread in threads:
            tasks = task_store.list_tasks_by_thread(thread["thread_id"])
            for task in tasks:
                writer.writerow([
                    thread["thread_id"],
                    task.get("task_id"),
                    task.get("status"),
                    task.get("created_at"),
                    task.get("updated_at"),
                    len(task.get("messages", [])),
                    task.get("duration_ms"),
                ])
        
        csv_str = output.getvalue()
        
        return StreamingResponse(
            io.BytesIO(csv_str.encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


def export_tasks(
    task_ids: list[str] | None = None,
    format: str = "json",
) -> StreamingResponse:
    """Export task details.
    
    Args:
        task_ids: List of task IDs to export. If None, export recent tasks.
        format: Export format - "json"
    
    Returns:
        StreamingResponse with exported data
    """
    if task_ids:
        tasks = [task_store.get_task(tid) for tid in task_ids]
        tasks = [t for t in tasks if t]
    else:
        tasks = task_store.list_tasks(limit=100)
    
    # Export as JSON
    json_str = json.dumps(tasks, indent=2, ensure_ascii=False, default=str)
    
    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        },
    )


def export_audit_log(
    limit: int = 1000,
    format: str = "json",
) -> StreamingResponse:
    """Export audit log.
    
    Args:
        limit: Maximum number of records to export
        format: Export format - "json" or "csv"
    
    Returns:
        StreamingResponse with exported data
    """
    from deepsupport_os.db.repositories import list_audit
    
    audit_records = list_audit(limit=limit)
    
    if format == "json":
        json_str = json.dumps(audit_records, indent=2, ensure_ascii=False, default=str)
        
        return StreamingResponse(
            io.BytesIO(json_str.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id",
            "task_id",
            "thread_id",
            "tool",
            "arguments",
            "result",
            "timestamp",
        ])
        
        # Write data
        for record in audit_records:
            writer.writerow([
                record.get("id"),
                record.get("task_id"),
                record.get("thread_id"),
                record.get("tool"),
                json.dumps(record.get("arguments", {}), ensure_ascii=False),
                json.dumps(record.get("result", {}), ensure_ascii=False),
                record.get("timestamp"),
            ])
        
        csv_str = output.getvalue()
        
        return StreamingResponse(
            io.BytesIO(csv_str.encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
