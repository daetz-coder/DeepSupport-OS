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

from deepagents.backends.protocol import (  # noqa: E402  (lightweight dataclasses)
    DeleteResult,
    EditResult,
    FileDownloadResponse,
    FileUploadResponse,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)

_sandbox: Any | None = None
_daytona_raw: Any | None = None
_daytona_client: Any | None = None
# Per-thread CompositeBackend cache (workspace isolation); not shared across threads.
_thread_backends: dict[str, Any] = {}
# Optional per-thread Daytona sandboxes when daytona_sandbox_scope=thread.
_daytona_by_thread: dict[str, Any] = {}
_sandbox_by_thread: dict[str, Any] = {}

SANDBOX_ROUTE = "/sandbox/"
SKILLS_ROUTE = "/skills/"
MEMORY_ROUTE = "/memory/"


class ReadOnlyFilesystemBackend:
    """FilesystemBackend wrapper that rejects writes outside an allow-list.

    deepagents' ``FilesystemBackend`` has no read-only mode, so shared mounts
    are writable by default. This wrapper blocks ``write`` / ``edit`` /
    ``delete`` / ``upload`` for any path not under a configured writable prefix
    and delegates everything else (``read`` / ``ls`` / ``glob`` / ``grep`` /
    ``download``) to the inner backend.

    Used for AR-02 / R1-5 isolation:
      - ``/skills/``   → ``writable_prefixes=()`` (fully read-only)
      - ``/memory/``   → ``writable_prefixes=("threads/",)`` so per-thread
                         session notes stay writable while ``org.md`` is not.

    Paths arrive from ``CompositeBackend`` already stripped of the route prefix
    (e.g. ``/memory/org.md`` → ``/org.md``), so writable prefixes are matched
    against the normalized relative path.
    """

    def __init__(
        self,
        root_dir: str | Path | None = None,
        *,
        writable_prefixes: tuple[str, ...] = (),
        virtual_mode: bool = True,
        max_file_size_mb: int = 10,
    ):
        from deepagents.backends import FilesystemBackend

        self._inner = FilesystemBackend(
            root_dir=root_dir, virtual_mode=virtual_mode, max_file_size_mb=max_file_size_mb
        )
        self._writable = tuple(
            str(p).replace("\\", "/").strip("/") for p in writable_prefixes if str(p).strip("/")
        )

    def _is_writable(self, path: str) -> bool:
        rel = str(path or "").replace("\\", "/").lstrip("/")
        return any(rel == p or rel.startswith(p + "/") for p in self._writable)

    def _deny(self, result_type: type, file_path: str, op: str):
        return result_type(
            error=f"readonly_path: {op} blocked for read-only mount '{file_path}'",
            path=str(file_path),
        )

    # ---- read-only ops (delegate to inner) ----

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return self._inner.read(file_path, offset=offset, limit=limit)

    def ls(self, path: str) -> LsResult:
        return self._inner.ls(path)

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        return self._inner.glob(pattern, path=path)

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None, **kw) -> GrepResult:
        return self._inner.grep(pattern, path=path, glob=glob, **kw)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return self._inner.download_files(paths)

    # ---- mutating ops (blocked unless path is writable) ----

    def write(self, file_path: str, content: str) -> WriteResult:
        if not self._is_writable(file_path):
            return self._deny(WriteResult, file_path, "write")
        return self._inner.write(file_path, content)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        if not self._is_writable(file_path):
            return self._deny(EditResult, file_path, "edit")
        return self._inner.edit(file_path, old_string, new_string, replace_all=replace_all)

    def delete(self, file_path: str) -> DeleteResult:
        if not self._is_writable(file_path):
            return self._deny(DeleteResult, file_path, "delete")
        return self._inner.delete(file_path)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        blocked = [path for path, _ in files if not self._is_writable(path)]
        if blocked:
            return [FileUploadResponse(path=p, error="permission_denied") for p in blocked]
        return self._inner.upload_files(files)

    # ---- async variants ----

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return await self._inner.aread(file_path, offset=offset, limit=limit)

    async def als(self, path: str) -> LsResult:
        return await self._inner.als(path)

    async def aglob(self, pattern: str, path: str | None = None) -> GlobResult:
        return await self._inner.aglob(pattern, path=path)

    async def agrep(self, pattern: str, path: str | None = None, glob: str | None = None, **kw) -> GrepResult:
        return await self._inner.agrep(pattern, path=path, glob=glob, **kw)

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return await self._inner.adownload_files(paths)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        if not self._is_writable(file_path):
            return self._deny(WriteResult, file_path, "write")
        return await self._inner.awrite(file_path, content)

    async def aedit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        if not self._is_writable(file_path):
            return self._deny(EditResult, file_path, "edit")
        return await self._inner.aedit(file_path, old_string, new_string, replace_all=replace_all)

    async def adelete(self, file_path: str) -> DeleteResult:
        if not self._is_writable(file_path):
            return self._deny(DeleteResult, file_path, "delete")
        return await self._inner.adelete(file_path)

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        blocked = [path for path, _ in files if not self._is_writable(path)]
        if blocked:
            return [FileUploadResponse(path=p, error="permission_denied") for p in blocked]
        return await self._inner.aupload_files(files)


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


def get_or_create_daytona_backend(thread_id: str | None = None) -> Any | None:
    """Raw DaytonaSandbox. Prefer build_hybrid_backend().

    When ``thread_id`` is set, uses a dedicated sandbox name
    ``{base}-{tid}`` so threads do not share a writable cloud FS.
    """
    global _sandbox, _daytona_raw, _daytona_client
    settings = get_settings()
    if not settings.daytona_enabled:
        return None
    if not settings.daytona_api_key:
        logger.warning("DAYTONA_ENABLED but DAYTONA_API_KEY empty; local-only backend")
        return None

    from deepsupport_os.harness.workspace import sanitize_thread_id

    tid_key = sanitize_thread_id(thread_id) if thread_id else None
    if tid_key:
        cached = _daytona_by_thread.get(tid_key)
        if cached is not None:
            return cached
    elif _daytona_raw is not None:
        return _daytona_raw

    _ensure_env()
    try:
        from daytona import CreateSandboxFromSnapshotParams, Daytona
        from langchain_daytona import DaytonaSandbox
    except ImportError as exc:
        logger.warning("daytona packages missing: %s", exc)
        return None

    base = settings.daytona_sandbox_name or "deepsupport-sandbox"
    name = f"{base}-{tid_key[:40]}" if tid_key else base
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

        raw = DaytonaSandbox(sandbox=sandbox)
        if tid_key:
            _sandbox_by_thread[tid_key] = sandbox
            _daytona_by_thread[tid_key] = raw
        else:
            _sandbox = sandbox
            _daytona_raw = raw
        return raw
    except Exception as exc:  # noqa: BLE001
        logger.warning("daytona unavailable, local-only: %s", exc)
        if not tid_key:
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
    """CompositeBackend with forced path isolation (AR-02 / R1-5 / R2-4).

    - default + ``/workspace/{tid}/`` → thread workspace (writable + execute)
    - ``/skills/`` → repo skills (read via FilesystemBackend)
    - ``/memory/`` → memory/ (org + per-thread AGENTS under threads/{tid}/)
    - ``/sandbox/`` → scope-dependent (default: local workspace sandbox, not shared Daytona)
    """
    from deepagents.backends import CompositeBackend, FilesystemBackend

    from deepsupport_os.harness.workspace import ensure_thread_workspace, sanitize_thread_id

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
        # /skills/ fully read-only; /memory/ only per-thread session notes writable
        # (org.md stays read-only) — AR-02 / R1-5.
        SKILLS_ROUTE: ReadOnlyFilesystemBackend(root_dir=skills_root, virtual_mode=True),
        MEMORY_ROUTE: ReadOnlyFilesystemBackend(
            root_dir=memory_root, virtual_mode=True, writable_prefixes=("threads/",)
        ),
    }

    scope = (settings.daytona_sandbox_scope or "local").strip().lower()
    mode = (settings.daytona_mode or "sidecar").strip().lower()

    if attach_daytona and mode not in {"off", "false", "0", "disabled"}:
        if mode == "full" and scope in {"shared", "thread"}:
            remote = get_or_create_daytona_backend(
                thread_id=tid if scope == "thread" else None
            )
            if remote is not None:
                _thread_backends[cache_key] = remote
                return remote
        elif scope == "local":
            sandbox_dir = ensure_thread_workspace(tid) / "sandbox"
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            routes[SANDBOX_ROUTE] = FilesystemBackend(
                root_dir=sandbox_dir, virtual_mode=True
            )
        elif scope == "shared":
            remote = get_or_create_daytona_backend()
            if remote is not None:
                routes[SANDBOX_ROUTE] = remote
        elif scope == "thread":
            remote = get_or_create_daytona_backend(thread_id=tid)
            if remote is not None:
                routes[SANDBOX_ROUTE] = remote
        # scope=off → no /sandbox/ route

    hybrid = CompositeBackend(default=ws_backend, routes=routes)
    _thread_backends[cache_key] = hybrid
    logger.info(
        "thread backend ready tid=%s scope=%s routes=%s",
        tid,
        scope,
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
    settings = get_settings()
    scope = (settings.daytona_sandbox_scope or "local").strip().lower()
    if scope in {"local", "off"}:
        return {
            "ok": False,
            "error": "daytona_shell_disabled",
            "hint": "DAYTONA_SANDBOX_SCOPE=local|off uses thread-local /sandbox/ files; set shared|thread for cloud shell",
            "scope": scope,
        }
    from deepsupport_os.harness.runtime_context import get_thread_id

    thread_id = get_thread_id() if scope == "thread" else None
    backend = get_or_create_daytona_backend(thread_id=thread_id)
    if backend is None:
        return {"ok": False, "error": "daytona_unavailable", "hint": "DAYTONA_ENABLED / API key / sandbox started?"}
    try:
        result = backend.execute(cmd, timeout=30)
        output = getattr(result, "output", None) or getattr(result, "result", None) or str(result)
        exit_code = getattr(result, "exit_code", None)
        return {"ok": True, "exit_code": exit_code, "output": str(output)[:4000], "scope": scope}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def cleanup_daytona(*, stop: bool = False, delete: bool = False) -> None:
    global _sandbox, _daytona_raw, _daytona_client, _thread_backends, _daytona_by_thread, _sandbox_by_thread
    client = _daytona_client
    sandboxes = []
    if _sandbox is not None:
        sandboxes.append(_sandbox)
    sandboxes.extend(_sandbox_by_thread.values())
    if client is None or not sandboxes:
        _thread_backends.clear()
        _daytona_by_thread.clear()
        _sandbox_by_thread.clear()
        return
    try:
        for sandbox in sandboxes:
            try:
                if delete:
                    client.delete(sandbox)
                elif stop:
                    client.stop(sandbox)
            except Exception as exc:  # noqa: BLE001
                logger.warning("daytona cleanup failed: %s", exc)
    finally:
        _sandbox = None
        _daytona_raw = None
        _daytona_client = None
        _thread_backends.clear()
        _daytona_by_thread.clear()
        _sandbox_by_thread.clear()


def clear_thread_backends(thread_id: str | None = None) -> None:
    """Drop cached backends (all, or one thread).

    Also drops the per-thread Daytona sandbox references, otherwise
    ``/delete_thread`` in ``scope=thread`` mode leaked ``_daytona_by_thread`` /
    ``_sandbox_by_thread`` entries for every deleted conversation.
    """
    if thread_id is None:
        _thread_backends.clear()
        _daytona_by_thread.clear()
        _sandbox_by_thread.clear()
        return
    from deepsupport_os.harness.workspace import sanitize_thread_id

    tid = sanitize_thread_id(thread_id)
    for key in list(_thread_backends):
        if key.startswith(f"{tid}:"):
            _thread_backends.pop(key, None)
    _daytona_by_thread.pop(tid, None)
    _sandbox_by_thread.pop(tid, None)


def probe_sandbox_status() -> dict[str, Any]:
    """Lightweight Sandbox/Daytona status for UI (does not create a sandbox)."""
    settings = get_settings()
    mode = (settings.daytona_mode or "sidecar").strip().lower()
    scope = (settings.daytona_sandbox_scope or "local").strip().lower()
    base: dict[str, Any] = {
        "enabled": bool(settings.daytona_enabled),
        "mode": mode,
        "scope": scope,
        "name": settings.daytona_sandbox_name or "deepsupport-sandbox",
        "api_key_configured": bool(settings.daytona_api_key),
        "route": SANDBOX_ROUTE,
    }
    if scope in {"local", "off"}:
        return {
            **base,
            "ok": True,
            "status": "local" if scope == "local" else "off",
            "detail": (
                "/sandbox/ → workspace/{tid}/sandbox/（thread 隔离，无共享云沙箱）"
                if scope == "local"
                else "未挂载 /sandbox/ 路由"
            ),
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
