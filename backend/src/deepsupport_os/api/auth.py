"""Optional admin token for mutating management endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException

from deepsupport_os.core.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    """When ADMIN_TOKEN is set, require matching X-Admin-Token header.

    Empty ADMIN_TOKEN keeps local demo open (no auth).
    """
    expected = (get_settings().admin_token or "").strip()
    if not expected:
        return
    if not x_admin_token or x_admin_token.strip() != expected:
        raise HTTPException(
            status_code=401,
            detail="missing or invalid X-Admin-Token (set ADMIN_TOKEN in .env)",
        )
