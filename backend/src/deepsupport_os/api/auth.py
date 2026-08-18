"""Optional admin header + demo passphrase cookie."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from deepsupport_os.core.config import get_settings

DEMO_COOKIE = "ds_demo"

router = APIRouter(prefix="/auth/demo", tags=["auth"])


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


def _demo_secret() -> str:
    return (get_settings().demo_access_token or "").strip()


def _cookie_digest() -> str:
    secret = _demo_secret()
    return hmac.new(secret.encode("utf-8"), b"ds-demo-v1", hashlib.sha256).hexdigest()


def _cookie_ok(got: str | None) -> bool:
    if not got:
        return False
    expected = _cookie_digest()
    if len(got) != len(expected):
        return False
    return hmac.compare_digest(got, expected)


def require_demo(request: Request) -> None:
    """When DEMO_ACCESS_TOKEN is set, require the httponly demo cookie."""
    if not _demo_secret():
        return
    if not _cookie_ok(request.cookies.get(DEMO_COOKIE)):
        raise HTTPException(status_code=401, detail="demo_auth_required")


class DemoLoginBody(BaseModel):
    passphrase: str = Field(min_length=1, max_length=256)


@router.get("/status")
def demo_status(request: Request):
    required = bool(_demo_secret())
    if not required:
        return {"required": False, "ok": True}
    return {"required": True, "ok": _cookie_ok(request.cookies.get(DEMO_COOKIE))}


@router.post("/login")
def demo_login(body: DemoLoginBody, response: Response):
    expected = _demo_secret()
    if not expected:
        return {"ok": True, "required": False}
    got = body.passphrase.strip().encode("utf-8")
    want = expected.encode("utf-8")
    if len(got) != len(want) or not hmac.compare_digest(got, want):
        raise HTTPException(status_code=401, detail="invalid_passphrase")
    settings = get_settings()
    path = (settings.demo_cookie_path or "/").strip() or "/"
    response.set_cookie(
        key=DEMO_COOKIE,
        value=_cookie_digest(),
        httponly=True,
        samesite="lax",
        secure=False,
        path=path,
        max_age=60 * 60 * 24 * 7,
    )
    return {"ok": True, "required": True}


@router.post("/logout")
def demo_logout(response: Response):
    path = (get_settings().demo_cookie_path or "/").strip() or "/"
    response.delete_cookie(DEMO_COOKIE, path=path)
    return {"ok": True}
