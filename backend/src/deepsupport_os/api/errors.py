"""Unified error handling and response formatting."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class DeepSupportError(Exception):
    """Base exception for DeepSupport OS."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "unknown_error",
        status_code: int = 500,
        metadata: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.metadata = metadata or {}
        super().__init__(message)


class NotFoundError(DeepSupportError):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} 不存在: {identifier}",
            error_code="not_found",
            status_code=404,
            metadata={"resource": resource, "identifier": identifier},
        )


class ValidationError(DeepSupportError):
    """Validation error."""
    
    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=400,
            metadata={"field": field} if field else {},
        )


class RateLimitError(DeepSupportError):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int, limit: int):
        super().__init__(
            message=f"请求过于频繁，请在 {retry_after} 秒后重试",
            error_code="rate_limit_exceeded",
            status_code=429,
            metadata={"retry_after": retry_after, "limit": limit},
        )


class AuthenticationError(DeepSupportError):
    """Authentication failed."""
    
    def __init__(self, message: str = "认证失败"):
        super().__init__(
            message=message,
            error_code="authentication_failed",
            status_code=401,
        )


class AuthorizationError(DeepSupportError):
    """Authorization failed."""
    
    def __init__(self, message: str = "权限不足"):
        super().__init__(
            message=message,
            error_code="authorization_failed",
            status_code=403,
        )


async def deepsupport_error_handler(request: Request, exc: DeepSupportError):
    """Handle DeepSupportError exceptions."""
    logger.error(
        f"DeepSupportError: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "metadata": exc.metadata,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException."""
    logger.error(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": str(exc.detail),
            "status_code": exc.status_code,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle generic exceptions."""
    logger.exception(
        f"Unhandled exception: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "服务器内部错误，请稍后重试",
            "details": str(exc) if __debug__ else None,
        },
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(DeepSupportError, deepsupport_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


def success_response(
    data: Any = None,
    message: str = "操作成功",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a standardized success response."""
    response = {
        "success": True,
        "message": message,
    }
    
    if data is not None:
        response["data"] = data
    
    if metadata:
        response["metadata"] = metadata
    
    return response


def error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a standardized error response."""
    response = {
        "success": False,
        "error": error_code,
        "message": message,
    }
    
    if metadata:
        response["metadata"] = metadata
    
    return response
