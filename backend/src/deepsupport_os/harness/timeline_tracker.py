"""Timeline tracker for agent execution visualization and audit."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class TimelineSpan:
    """Represents a single operation in the timeline."""
    
    id: str
    name: str
    kind: str  # "agent", "tool", "skill", "subagent", "llm"
    parent_id: str | None
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    status: str = "running"  # "running", "completed", "failed"
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
            "children": self.children,
        }


class TimelineTracker:
    """Thread-safe timeline tracker for agent execution."""
    
    def __init__(self):
        self._spans: dict[str, TimelineSpan] = {}
        self._lock = threading.Lock()
        self._root_span_id: str | None = None
    
    def start_span(
        self,
        name: str,
        kind: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Start a new span and return its ID."""
        span_id = str(uuid4())
        span = TimelineSpan(
            id=span_id,
            name=name,
            kind=kind,
            parent_id=parent_id,
            start_time=time.time(),
            metadata=metadata or {},
        )
        
        with self._lock:
            self._spans[span_id] = span
            if parent_id and parent_id in self._spans:
                self._spans[parent_id].children.append(span_id)
            if self._root_span_id is None:
                self._root_span_id = span_id
        
        return span_id
    
    def end_span(
        self,
        span_id: str,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a span and record its duration."""
        with self._lock:
            if span_id not in self._spans:
                return
            
            span = self._spans[span_id]
            span.end_time = time.time()
            span.duration_ms = (span.end_time - span.start_time) * 1000
            span.status = status
            
            if metadata:
                span.metadata.update(metadata)
    
    def get_timeline(self) -> list[dict[str, Any]]:
        """Get the complete timeline as a list of spans."""
        with self._lock:
            return [span.to_dict() for span in self._spans.values()]
    
    def get_tree(self) -> dict[str, Any] | None:
        """Get the timeline as a tree structure."""
        if not self._root_span_id:
            return None
        
        with self._lock:
            def build_tree(span_id: str) -> dict[str, Any]:
                span = self._spans[span_id]
                result = span.to_dict()
                result["children"] = [
                    build_tree(child_id) for child_id in span.children
                ]
                return result
            
            return build_tree(self._root_span_id)
    
    def clear(self) -> None:
        """Clear all spans."""
        with self._lock:
            self._spans.clear()
            self._root_span_id = None


# Global timeline tracker instance
_timeline_tracker = TimelineTracker()


def get_timeline_tracker() -> TimelineTracker:
    """Get the global timeline tracker instance."""
    return _timeline_tracker
