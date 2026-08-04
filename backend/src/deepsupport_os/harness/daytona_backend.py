"""Daytona sandbox backend for Deep Agents (skills / shell isolation)."""

from __future__ import annotations

import logging
import os
from typing import Any

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)

_sandbox: Any | None = None
_backend: Any | None = None
_daytona_client: Any | None = None


def _ensure_env() -> None:
    settings = get_settings()
    if settings.daytona_api_key:
        os.environ["DAYTONA_API_KEY"] = settings.daytona_api_key
    if settings.daytona_api_url:
        os.environ.setdefault("DAYTONA_API_URL", settings.daytona_api_url)
    if settings.daytona_target:
        os.environ["DAYTONA_TARGET"] = settings.daytona_target


def _sandbox_state(sandbox: Any) -> str:
    return str(getattr(sandbox, "state", "") or getattr(sandbox, "status", "") or "").lower()


def get_or_create_daytona_backend() -> Any | None:
    """Return a DaytonaSandbox backend, or None when disabled / unavailable."""
    global _sandbox, _backend, _daytona_client
    settings = get_settings()
    if not settings.daytona_enabled:
        return None
    if not settings.daytona_api_key:
        logger.warning("DAYTONA_ENABLED but DAYTONA_API_KEY empty; using local workspace")
        return None
    if _backend is not None:
        return _backend

    _ensure_env()
    try:
        from daytona import CreateSandboxFromSnapshotParams, Daytona
        from langchain_daytona import DaytonaSandbox
    except ImportError as exc:
        logger.warning("daytona packages missing: %s", exc)
        return None

    name = settings.daytona_sandbox_name or "deepsupport-sandbox"
    try:
        client = Daytona()
        _daytona_client = client

        sandbox = None
        try:
            sandbox = client.get(name)
            state = _sandbox_state(sandbox)
            if state not in {"started", "running", "ready"}:
                logger.info("starting daytona sandbox %s (state=%s)", name, state)
                client.start(sandbox, timeout=120)
            logger.info("reusing daytona sandbox %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.info("daytona get(%s) failed (%s); creating", name, exc)
            sandbox = client.create(
                CreateSandboxFromSnapshotParams(name=name, language="python"),
                timeout=120,
            )
            logger.info("created daytona sandbox %s id=%s", name, getattr(sandbox, "id", "?"))

        _sandbox = sandbox
        _backend = DaytonaSandbox(sandbox=sandbox)
        return _backend
    except Exception as exc:  # noqa: BLE001
        logger.warning("daytona backend unavailable, falling back to local FS: %s", exc)
        _sandbox = None
        _backend = None
        _daytona_client = None
        return None


def cleanup_daytona(*, stop: bool = False, delete: bool = False) -> None:
    """Optional lifecycle cleanup (stop/delete named sandbox)."""
    global _sandbox, _backend, _daytona_client
    if _daytona_client is None or _sandbox is None:
        return
    try:
        if delete:
            _daytona_client.delete(_sandbox)
        elif stop:
            _daytona_client.stop(_sandbox)
    except Exception as exc:  # noqa: BLE001
        logger.warning("daytona cleanup failed: %s", exc)
    finally:
        _sandbox = None
        _backend = None
        _daytona_client = None
