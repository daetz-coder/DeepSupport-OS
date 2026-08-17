"""Session management for DeepSupport OS."""

from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException, Request


class SessionManager:
    """Manage user sessions with timeout."""
    
    def __init__(self, timeout_minutes: int = 30):
        self.timeout_minutes = timeout_minutes
        self.sessions: dict[str, dict[str, Any]] = {}
    
    def create_session(self, session_id: str, user_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new session."""
        self.sessions[session_id] = {
            "user_data": user_data,
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session if valid."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Check timeout
        elapsed = time.time() - session["last_activity"]
        if elapsed > self.timeout_minutes * 60:
            # Session expired
            del self.sessions[session_id]
            return None
        
        # Update last activity
        session["last_activity"] = time.time()
        return session
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self.sessions.pop(session_id, None)
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session["last_activity"] > self.timeout_minutes * 60
        ]
        for sid in expired:
            del self.sessions[sid]
        return len(expired)


# Global session manager
session_manager = SessionManager(timeout_minutes=30)


def get_session_from_request(request: Request) -> dict[str, Any]:
    """Extract and validate session from request."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=401, detail="Missing session ID")
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    
    return session


def create_session_endpoint():
    """Create a new session."""
    import uuid
    
    session_id = str(uuid.uuid4())
    session = session_manager.create_session(session_id, {})
    return {
        "session_id": session_id,
        "created_at": session["created_at"],
    }


def validate_session(request: Request):
    """Validate session middleware."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        # Allow requests without session for now (backward compatibility)
        return
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
