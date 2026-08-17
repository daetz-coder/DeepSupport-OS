"""Data export functionality for conversation history and artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from deepsupport_os.db.task_store import list_tasks, get_task
from deepsupport_os.harness.workspace import ensure_thread_workspace


def export_conversation_history(
    thread_id: str,
    format: str = "json",
) -> dict[str, Any]:
    """Export conversation history for a thread.
    
    Args:
        thread_id: Thread ID to export
        format: Export format ("json" or "markdown")
    
    Returns:
        dict with export data and metadata
    """
    tasks = list_tasks(limit=1000, thread_id=thread_id)
    
    if format == "json":
        return {
            "format": "json",
            "thread_id": thread_id,
            "exported_at": datetime.utcnow().isoformat(),
            "task_count": len(tasks),
            "tasks": tasks,
        }
    
    elif format == "markdown":
        md_lines = [
            f"# Conversation History",
            f"",
            f"**Thread ID:** {thread_id}",
            f"**Exported At:** {datetime.utcnow().isoformat()}",
            f"**Task Count:** {len(tasks)}",
            f"",
            f"---",
            f"",
        ]
        
        for task in tasks:
            md_lines.append(f"## Task: {task.get('task_id', 'N/A')}")
            md_lines.append(f"")
            md_lines.append(f"**Status:** {task.get('status', 'N/A')}")
            md_lines.append(f"**Created:** {task.get('created_at', 'N/A')}")
            md_lines.append(f"")
            
            messages = task.get("messages", [])
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                md_lines.append(f"### {role.capitalize()}")
                md_lines.append(f"")
                md_lines.append(content)
                md_lines.append(f"")
            
            md_lines.append(f"---")
            md_lines.append(f"")
        
        return {
            "format": "markdown",
            "thread_id": thread_id,
            "exported_at": datetime.utcnow().isoformat(),
            "content": "\n".join(md_lines),
        }
    
    else:
        raise ValueError(f"Unsupported format: {format}")


def export_artifacts(thread_id: str) -> dict[str, Any]:
    """Export all artifacts for a thread.
    
    Args:
        thread_id: Thread ID to export
    
    Returns:
        dict with artifact data
    """
    workspace = ensure_thread_workspace(thread_id)
    
    artifacts = []
    if workspace.exists():
        for file_path in workspace.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    artifacts.append({
                        "path": str(file_path.relative_to(workspace)),
                        "size": file_path.stat().st_size,
                        "content": content,
                    })
                except Exception:
                    # Skip binary or unreadable files
                    pass
    
    return {
        "thread_id": thread_id,
        "exported_at": datetime.utcnow().isoformat(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def export_full_thread(thread_id: str) -> dict[str, Any]:
    """Export complete thread data including history and artifacts.
    
    Args:
        thread_id: Thread ID to export
    
    Returns:
        dict with complete thread data
    """
    history = export_conversation_history(thread_id, format="json")
    artifacts = export_artifacts(thread_id)
    
    return {
        "thread_id": thread_id,
        "exported_at": datetime.utcnow().isoformat(),
        "history": history,
        "artifacts": artifacts,
    }


def save_export(data: dict[str, Any], output_path: str | Path) -> Path:
    """Save export data to file.
    
    Args:
        data: Export data to save
        output_path: Output file path
    
    Returns:
        Path to saved file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return output_path
