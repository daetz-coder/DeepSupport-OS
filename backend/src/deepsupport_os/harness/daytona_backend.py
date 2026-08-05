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
# Per-thread CompositeBackend cache (workspace isolation); not shared across threads.
_thread_backends: dict[str, Any] = {}

SANDBOX_ROUTE = "/sandbox/"
SKILLS_ROUTE = "/skills/"
MEMORY_ROUTE = "/memory/"


def _ensure_env() -> None:
    settings = get_settings()
    if settings.daytona_api_key:
        os.environ["DAYTONA_API_KEY"] = settings.daytona_api_key
    if settings.daytona_api_url:
        os.environ.setdefault("DAYTONA_API_URL", settings.daytona_api_url)
    if settings.daytona_target:
        os.environ["DAYTONA_TARGET"] = settings.daytona_target


def _sandbox_state(sandbox: Any) -> str:
    """Normalize Daytona state enum/string to a short token (e.g. started)."""
    raw = getattr(sandbox, "state", None)
    if raw is None:
        raw = getattr(sandbox, "status", None)
    if raw is None:
        return ""
    if hasattr(raw, "value"):
        raw = raw.value
    text = str(raw).strip().lower()
    # Enum repr like "SandboxState.STARTED" / "sandboxstate.started"
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


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


def build_local_backend(*, thread_id: str | None = None):
    """Local backend rooted at the thread workspace (or workspace root)."""
    from deepagents.backends import LocalShellBackend

    from deepsupport_os.harness.workspace import ensure_thread_workspace, sanitize_thread_id

    settings = get_settings()
    if thread_id:
        root = ensure_thread_workspace(sanitize_thread_id(thread_id))
    else:
        root = settings.resolve(settings.workspace_dir)
        root.mkdir(parents=True, exist_ok=True)
    return LocalShellBackend(root_dir=root, timeout=60)


def build_thread_backend(
    thread_id: str | None = None,
    *,
    attach_daytona: bool = True,
):
    """CompositeBackend with forced path isolation (AR-02 / R1-5).

    - default + ``/workspace/{tid}/`` → thread workspace (writable + execute)
    - ``/skills/`` → repo skills (read via FilesystemBackend)
    - ``/memory/`` → memory/ (org + per-thread AGENTS under threads/{tid}/)
    - ``/sandbox/`` → Daytona sidecar when enabled
    """
    from deepagents.backends import CompositeBackend, FilesystemBackend

    from deepsupport_os.harness.workspace import sanitize_thread_id

    settings = get_settings()
    tid = sanitize_thread_id(thread_id) if thread_id else "default"
    cache_key = f"{tid}:{'daytona' if attach_daytona else 'local'}"
    cached = _thread_backends.get(cache_key)
    if cached is not None:
        return cached

    ws_backend = build_local_backend(thread_id=tid)
    skills_root = settings.resolve("skills")
    memory_root = settings.resolve("memory")
    memory_root.mkdir(parents=True, exist_ok=True)

    routes: dict[str, Any] = {
        f"/workspace/{tid}/": ws_backend,
        SKILLS_ROUTE: FilesystemBackend(root_dir=skills_root, virtual_mode=True),
        MEMORY_ROUTE: FilesystemBackend(root_dir=memory_root, virtual_mode=True),
    }

    if attach_daytona:
        mode = (settings.daytona_mode or "sidecar").strip().lower()
        if mode not in {"off", "false", "0", "disabled"}:
            if mode == "full":
                remote = get_or_create_daytona_backend()
                if remote is not None:
                    _thread_backends[cache_key] = remote
                    return remote
            else:
                remote = get_or_create_daytona_backend()
                if remote is not None:
                    routes[SANDBOX_ROUTE] = remote

    hybrid = CompositeBackend(default=ws_backend, routes=routes)
    _thread_backends[cache_key] = hybrid
    logger.info(
        "thread backend ready tid=%s routes=%s",
        tid,
        sorted(routes.keys()),
    )
    return hybrid


def build_hybrid_backend(
    thread_id: str | None = None,
    *,
    attach_daytona: bool = True,
):
    """Alias for build_thread_backend (keeps older call sites working)."""
    return build_thread_backend(thread_id=thread_id, attach_daytona=attach_daytona)


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
    global _sandbox, _daytona_raw, _daytona_client, _thread_backends
    if _daytona_client is None or _sandbox is None:
        _thread_backends.clear()
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
        _thread_backends.clear()


def clear_thread_backends(thread_id: str | None = None) -> None:
    """Drop cached CompositeBackends (all, or one thread)."""
    if thread_id is None:
        _thread_backends.clear()
        return
    from deepsupport_os.harness.workspace import sanitize_thread_id

    tid = sanitize_thread_id(thread_id)
    for key in list(_thread_backends):
        if key.startswith(f"{tid}:"):
            _thread_backends.pop(key, None)


def probe_sandbox_status() -> dict[str, Any]:
    """Lightweight Sandbox/Daytona status for UI (does not create a sandbox)."""
    settings = get_settings()
    mode = (settings.daytona_mode or "sidecar").strip().lower()
    base: dict[str, Any] = {
        "enabled": bool(settings.daytona_enabled),
        "mode": mode,
        "name": settings.daytona_sandbox_name or "deepsupport-sandbox",
        "api_key_configured": bool(settings.daytona_api_key),
        "route": SANDBOX_ROUTE,
    }
    if not settings.daytona_enabled or mode in {"off", "false", "0", "disabled"}:
        return {
            **base,
            "ok": False,
            "status": "disabled",
            "detail": "DAYTONA_ENABLED=false 或 DAYTONA_MODE=off",
        }
    if not settings.daytona_api_key:
        return {
            **base,
            "ok": False,
            "status": "unconfigured",
            "detail": "缺少 DAYTONA_API_KEY",
        }

    if _daytona_raw is not None and _sandbox is not None:
        state = _sandbox_state(_sandbox)
        return {
            **base,
            "ok": True,
            "status": "ready",
            "state": state or "cached",
            "cached": True,
        }

    _ensure_env()
    try:
        from daytona import Daytona
    except ImportError as exc:
        return {
            **base,
            "ok": False,
            "status": "missing_package",
            "detail": str(exc),
        }

    try:
        client = Daytona()
        # Bound cloud lookup so /api/health/deps cannot hang forever.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(client.get, base["name"])
            sandbox = fut.result(timeout=8)
        state = _sandbox_state(sandbox)
        ok = state in {"started", "running", "ready"}
        return {
            **base,
            "ok": ok,
            "status": "ready" if ok else "stopped",
            "state": state or "unknown",
            "cached": False,
            "detail": None if ok else "沙箱存在但未处于运行态（首次任务时可能自动 start）",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "ok": False,
            "status": "unreachable",
            "detail": str(exc)[:240],
        }
