"""Daytona as a lightweight sidecar — local FS/skills stay primary.

Daytona sandbox specs are small (≈1 vCPU / 1 GiB). Heavy work (Skills, RAG
offload, long reports) runs on local Filesystem/LocalShell. Daytona is only
mounted under `/sandbox/` for simple isolated file ops, plus an optional
shell tool for trivial remote commands.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)

_sandbox: Any | None = None
_daytona_raw: Any | None = None
_daytona_client: Any | None = None
_hybrid_backend: Any | None = None

SANDBOX_ROUTE = "/sandbox/"


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
    """Raw DaytonaSandbox instance (may be slow). Prefer build_hybrid_backend()."""
    global _sandbox, _daytona_raw, _daytona_client
    settings = get_settings()
    if not settings.daytona_enabled:
        return None
    if not settings.daytona_api_key:
        logger.warning("DAYTONA_ENABLED but DAYTONA_API_KEY empty; local-only backend")
        return None
    if _daytona_raw is not None:
        return _daytona_raw

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
        _daytona_raw = DaytonaSandbox(sandbox=sandbox)
        return _daytona_raw
    except Exception as exc:  # noqa: BLE001
        logger.warning("daytona unavailable, local-only: %s", exc)
        _sandbox = None
        _daytona_raw = None
        _daytona_client = None
        return None


def build_local_backend():
    """Fast local backend: Skills + workspace + shell on this machine."""
    from deepagents.backends import LocalShellBackend

    settings = get_settings()
    return LocalShellBackend(root_dir=settings.root_dir, timeout=60)


def build_hybrid_backend(*, attach_daytona: bool = True):
    """Local-first CompositeBackend; Daytona only under /sandbox/ when available.

    - default: LocalShellBackend (skills, workspace, execute — fast)
    - /sandbox/: Daytona (simple isolated snippets only)
    """
    global _hybrid_backend
    if _hybrid_backend is not None and attach_daytona:
        return _hybrid_backend

    local = build_local_backend()
    if not attach_daytona:
        return local

    settings = get_settings()
    mode = (settings.daytona_mode or "sidecar").strip().lower()
    if mode in {"off", "false", "0", "disabled"}:
        return local

    if mode == "full":
        # Legacy: entire agent FS on Daytona — slow on 1vCPU/1GiB; not recommended.
        remote = get_or_create_daytona_backend()
        return remote or local

    # sidecar (default)
    remote = get_or_create_daytona_backend()
    if remote is None:
        return local

    from deepagents.backends import CompositeBackend

    hybrid = CompositeBackend(default=local, routes={SANDBOX_ROUTE: remote})
    _hybrid_backend = hybrid
    logger.info("hybrid backend ready: local primary + daytona route %s", SANDBOX_ROUTE)
    return hybrid


@tool
def run_sandbox_shell(command: str) -> dict:
    """在云端 Daytona 沙箱执行**简单** shell（echo/短脚本）。复杂检索、Skills、长报告请用本地工作区。"""
    cmd = (command or "").strip()
    if not cmd:
        return {"ok": False, "error": "empty_command"}
    if len(cmd) > 500:
        return {"ok": False, "error": "command_too_long", "hint": "keep sandbox commands trivial"}
    backend = get_or_create_daytona_backend()
    if backend is None:
        return {"ok": False, "error": "daytona_unavailable", "hint": "DAYTONA_ENABLED / API key / sandbox started?"}
    try:
        result = backend.execute(cmd, timeout=30)
        output = getattr(result, "output", None) or getattr(result, "result", None) or str(result)
        exit_code = getattr(result, "exit_code", None)
        return {"ok": True, "exit_code": exit_code, "output": str(output)[:4000]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def cleanup_daytona(*, stop: bool = False, delete: bool = False) -> None:
    global _sandbox, _daytona_raw, _daytona_client, _hybrid_backend
    if _daytona_client is None or _sandbox is None:
        _hybrid_backend = None
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
        _daytona_raw = None
        _daytona_client = None
        _hybrid_backend = None
