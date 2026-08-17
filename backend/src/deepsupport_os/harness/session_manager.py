"""Session management and timeout handling."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class SessionManager:
    """Manage user sessions with automatic timeout."""
    
    def __init__(self, timeout_minutes: int = 30):
        self.timeout_minutes = timeout_minutes
        self.sessions: dict[str, dict[str, Any]] = {}
        self.last_activity: dict[str, float] = {}
    
    def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new session."""
        now = time.time()
        self.sessions[session_id] = {
            "created_at": now,
            "metadata": metadata or {},
        }
        self.last_activity[session_id] = now
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session if it exists and is not expired."""
        if session_id not in self.sessions:
            return None
        
        # Check timeout
        last_active = self.last_activity.get(session_id, 0)
        if time.time() - last_active > self.timeout_minutes * 60:
            self.expire_session(session_id)
            return None
        
        return self.sessions[session_id]
    
    def update_activity(self, session_id: str) -> None:
        """Update last activity time for a session."""
        if session_id in self.sessions:
            self.last_activity[session_id] = time.time()
    
    def expire_session(self, session_id: str) -> None:
        """Expire a session."""
        self.sessions.pop(session_id, None)
        self.last_activity.pop(session_id, None)
    
    def cleanup_expired(self) -> int:
        """Clean up all expired sessions. Returns number of sessions cleaned."""
        now = time.time()
        expired = [
            session_id
            for session_id, last_active in self.last_activity.items()
            if now - last_active > self.timeout_minutes * 60
        ]
        
        for session_id in expired:
            self.expire_session(session_id)
        
        return len(expired)
    
    def get_active_count(self) -> int:
        """Get count of active sessions."""
        return len(self.sessions)
    
    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        now = time.time()
        active_sessions = [
            sid for sid, last_active in self.last_activity.items()
            if now - last_active <= self.timeout_minutes * 60
        ]
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": len(active_sessions),
            "expired_sessions": len(self.sessions) - len(active_sessions),
            "timeout_minutes": self.timeout_minutes,
        }


# Global session manager
session_manager = SessionManager(timeout_minutes=30)


def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    return session_manager
