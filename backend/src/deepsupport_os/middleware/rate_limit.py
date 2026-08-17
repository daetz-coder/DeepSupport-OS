"""Rate limiting middleware to prevent API abuse."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
    
    def is_allowed(self, key: str) -> tuple[bool, dict[str, Any]]:
        """Check if request is allowed and return metadata."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > minute_ago
        ]
        
        # Check limit
        if len(self.requests[key]) >= self.requests_per_minute:
            retry_after = int(self.requests[key][0] + 60 - now)
            return False, {
                "retry_after": retry_after,
                "limit": self.requests_per_minute,
                "remaining": 0,
                "reset": int(self.requests[key][0] + 60),
            }
        
        # Allow request
        self.requests[key].append(now)
        remaining = self.requests_per_minute - len(self.requests[key])
        reset = int(self.requests[key][0] + 60) if self.requests[key] else int(now + 60)
        
        return True, {
            "retry_after": 0,
            "limit": self.requests_per_minute,
            "remaining": remaining,
            "reset": reset,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute)
    
    async def dispatch(self, request: Request, call_next):
        # Get client identifier (IP or API key)
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key", "")
        key = f"{client_ip}:{api_key}" if api_key else client_ip
        
        # Check rate limit
        allowed, metadata = self.limiter.is_allowed(key)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"请求过于频繁，请在 {metadata['retry_after']} 秒后重试",
                    "metadata": metadata,
                },
                headers={
                    "Retry-After": str(metadata["retry_after"]),
                    "X-RateLimit-Limit": str(metadata["limit"]),
                    "X-RateLimit-Remaining": str(metadata["remaining"]),
                    "X-RateLimit-Reset": str(metadata["reset"]),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
        response.headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
        response.headers["X-RateLimit-Reset"] = str(metadata["reset"])
        
        return response
