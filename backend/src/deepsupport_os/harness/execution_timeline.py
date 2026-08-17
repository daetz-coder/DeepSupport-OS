"""Execution timeline tracking for audit and debugging.

Tracks the complete execution flow with timing information:
- Main Agent execution
- SubAgent dispatches
- Tool calls
- Skill usage
- LLM calls

Provides a hierarchical timeline view for debugging and audit.
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from deepsupport_os.harness.runtime_context import get_task_id, get_thread_id


class ExecutionType(str, Enum):
    """Type of execution being tracked."""
    MAIN_AGENT = "main_agent"
    SUBAGENT = "subagent"
    TOOL = "tool"
    SKILL = "skill"
    LLM_CALL = "llm_call"


class ExecutionStatus(str, Enum):
    """Status of execution."""
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TimelineEvent:
    """Single event in the execution timeline."""
    id: str
    parent_id: Optional[str]
    event_type: ExecutionType
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: ExecutionStatus = ExecutionStatus.RUNNING
    input_data: Optional[dict[str, Any]] = None
    output_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["status"] = self.status.value
        # Remove None values for cleaner output
        return {k: v for k, v in data.items() if v is not None}


class ExecutionTimeline:
    """Tracks execution timeline with hierarchical parent-child relationships."""

    def __init__(self):
        self.events: list[TimelineEvent] = []
        self.active_events: dict[str, TimelineEvent] = {}  # event_id -> event
        self._lock = threading.Lock()
        self.task_id = get_task_id("")
        self.thread_id = get_thread_id() or ""

    def start_event(
        self,
        event_type: ExecutionType,
        name: str,
        parent_id: Optional[str] = None,
        input_data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Start tracking a new event. Returns event_id."""
        event_id = str(uuid4())
        event = TimelineEvent(
            id=event_id,
            parent_id=parent_id,
            event_type=event_type,
            name=name,
            start_time=time.time(),
            input_data=input_data,
            metadata=metadata or {},
        )
        
        with self._lock:
            self.events.append(event)
            self.active_events[event_id] = event
        
        return event_id

    def end_event(
        self,
        event_id: str,
        status: ExecutionStatus = ExecutionStatus.SUCCESS,
        output_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """End tracking an event."""
        with self._lock:
            event = self.active_events.pop(event_id, None)
            if event is None:
                return
            
            event.end_time = time.time()
            event.duration_ms = (event.end_time - event.start_time) * 1000
            event.status = status
            event.output_data = output_data
            event.error_message = error_message

    def get_timeline(self) -> list[dict[str, Any]]:
        """Get the complete timeline as a list of events."""
        with self._lock:
            return [event.to_dict() for event in self.events]

    def get_tree(self) -> dict[str, Any]:
        """Get timeline as a hierarchical tree structure."""
        with self._lock:
            events_by_id = {e.id: e.to_dict() for e in self.events}
            
            # Build tree structure
            root_events = []
            children_map: dict[str, list[dict[str, Any]]] = {}
            
            for event in self.events:
                event_dict = events_by_id[event.id]
                if event.parent_id is None:
                    root_events.append(event_dict)
                else:
                    if event.parent_id not in children_map:
                        children_map[event.parent_id] = []
                    children_map[event.parent_id].append(event_dict)
            
            # Attach children to parents
            def attach_children(event_dict: dict[str, Any]) -> dict[str, Any]:
                if event_dict["id"] in children_map:
                    event_dict["children"] = [
                        attach_children(child) 
                        for child in children_map[event_dict["id"]]
                    ]
                return event_dict
            
            return {
                "task_id": self.task_id,
                "thread_id": self.thread_id,
                "root_events": [attach_children(e) for e in root_events],
                "summary": self._get_summary(),
            }

    def _get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        total_duration = sum(e.duration_ms or 0 for e in self.events if e.duration_ms)
        
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        
        for event in self.events:
            type_key = event.event_type.value
            status_key = event.status.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            by_status[status_key] = by_status.get(status_key, 0) + 1
        
        return {
            "total_events": len(self.events),
            "total_duration_ms": total_duration,
            "by_type": by_type,
            "by_status": by_status,
        }


# Global timeline instance per task
_timelines: dict[str, ExecutionTimeline] = {}
_timelines_lock = threading.Lock()


def get_timeline(task_id: Optional[str] = None) -> ExecutionTimeline:
    """Get or create timeline for the current task."""
    tid = task_id or get_task_id("")
    with _timelines_lock:
        if tid not in _timelines:
            _timelines[tid] = ExecutionTimeline()
        return _timelines[tid]


def clear_timeline(task_id: Optional[str] = None) -> None:
    """Clear timeline for a task."""
    tid = task_id or get_task_id("")
    with _timelines_lock:
        _timelines.pop(tid, None)


def get_all_timelines() -> dict[str, dict[str, Any]]:
    """Get all timelines for debugging."""
    with _timelines_lock:
        return {tid: tl.get_tree() for tid, tl in _timelines.items()}
