"""Search API for conversation history."""

from fastapi import APIRouter, Query
from typing import Optional

from deepsupport_os.db.task_store import list_tasks

router = APIRouter(prefix="/search", tags=["search"])


def search_tasks(query: str, thread_id: Optional[str] = None, limit: int = 10, offset: int = 0):
    """Search tasks by content in messages."""
    all_tasks = list_tasks(limit=1000, thread_id=thread_id)
    results = []
    query_lower = query.lower()
    
    for task in all_tasks:
        # Search in messages
        for msg in task.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str) and query_lower in content.lower():
                results.append(task)
                break
        if len(results) >= limit + offset:
            break
    
    return results[offset:offset + limit]


@router.get("/tasks")
async def search_tasks_endpoint(
    q: str = Query(..., description="Search query"),
    thread_id: Optional[str] = Query(None, description="Filter by thread ID"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Search tasks by content."""
    results = search_tasks(
        query=q,
        thread_id=thread_id,
        limit=limit,
        offset=offset
    )
    return {
        "query": q,
        "total": len(results),
        "results": results
    }


@router.get("/threads")
async def search_threads_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Max results")
):
    """Search threads by content."""
    from deepsupport_os.db.task_store import list_threads
    
    all_threads = list_threads(limit=1000)
    results = []
    
    for thread in all_threads:
        # Search in thread preview
        if q.lower() in (thread.get("preview", "") or "").lower():
            results.append(thread)
        
        if len(results) >= limit:
            break
    
    return {
        "query": q,
        "total": len(results),
        "results": results
    }
