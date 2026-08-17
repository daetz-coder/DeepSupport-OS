"""Bridge nested subagent tool activity into the parent SSE stream.

DeepAgents' `task` tool calls `subagent.invoke()` synchronously, so the parent
`agent.stream()` loop sees nothing until the whole subagent finishes. LangChain
callbacks still fire during that nested invoke; we push them onto a queue and
drain it from a producer thread alongside parent stream chunks.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, Callable, Iterator
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

_PARENT = "parent"
_PROGRESS = "progress"
_ERROR = "error"
_DONE = "done"


def _clip(value: Any, limit: int = 800) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
    else:
        text = str(value)
    if len(text) <= limit:
        if isinstance(value, (dict, list)):
            return value
        return text
    return text[: limit - 3] + "..."


def _tool_name(serialized: dict[str, Any] | None, fallback: str = "tool") -> str:
    if not serialized:
        return fallback
    return str(
        serialized.get("name")
        or serialized.get("id")
        or (serialized.get("serialize") or {}).get("name")
        or fallback
    )


def _is_subagent_meta(metadata: dict[str, Any] | None, tags: list[str] | None) -> bool:
    md = metadata or {}
    if str(md.get("ls_agent_type") or "") == "subagent":
        return True
    cfg = md.get("configurable") if isinstance(md.get("configurable"), dict) else {}
    if str(cfg.get("ls_agent_type") or "") == "subagent":
        return True
    for t in tags or []:
        if "subagent" in str(t).lower():
            return True
    return False


class SubagentProgressHandler(BaseCallbackHandler):
    """Emit nested (subagent) tool/LLM lifecycle events onto a queue."""

    def __init__(self, bus: queue.Queue[tuple[str, Any]]):
        super().__init__()
        self._bus = bus
        self._task_depth = 0
        self._current_subagent = "unknown"
        self._lock = threading.Lock()

    def _emit(self, payload: dict[str, Any]) -> None:
        payload = {**payload, "subagent": payload.get("subagent") or self._current_subagent}
        logger.info(
            "subagent_progress phase=%s name=%s subagent=%s",
            payload.get("phase"),
            payload.get("name"),
            payload.get("subagent"),
        )
        self._bus.put((_PROGRESS, payload))

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = _tool_name(serialized)
        args = inputs if isinstance(inputs, dict) else None
        if name == "task":
            with self._lock:
                self._task_depth += 1
                if args:
                    self._current_subagent = str(
                        args.get("subagent_type")
                        or args.get("name")
                        or args.get("agent")
                        or self._current_subagent
                    )
            # Parent stream already emits subagent_dispatch; skip duplicate.
            return

        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        self._emit(
            {
                "phase": "tool_start",
                "kind": "tool_call",
                "name": name,
                "args": _clip(args if args is not None else input_str),
            }
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        ser = kwargs.get("serialized")
        resolved = str(name or "") or _tool_name(
            ser if isinstance(ser, dict) else None, "tool"
        )

        if resolved == "task":
            with self._lock:
                self._task_depth = max(0, self._task_depth - 1)
            return

        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        self._emit(
            {
                "phase": "tool_end",
                "kind": "tool_result",
                "name": resolved,
                "content": _clip(getattr(output, "content", output)),
            }
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        name = str(kwargs.get("name") or "tool")
        self._emit(
            {
                "phase": "tool_error",
                "kind": "tool_result",
                "name": name,
                "content": _clip(f"ERROR: {error}"),
            }
        )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        self._emit(
            {
                "phase": "llm_start",
                "kind": "assistant",
                "name": "llm",
                "content": f"{self._current_subagent} 思考中…",
            }
        )

    def on_chat_model_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Signal completion of subagent LLM call to clear 'thinking' state."""
        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        self._emit(
            {
                "phase": "llm_end",
                "kind": "assistant_done",
                "name": "llm",
                "content": f"{self._current_subagent} 已完成思考",
            }
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Signal LLM error to clear 'thinking' state."""
        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return
        self._emit(
            {
                "phase": "llm_error",
                "kind": "assistant_error",
                "name": "llm",
                "content": f"{self._current_subagent} LLM 调用失败: {error}",
            }
        )


def run_stream_with_progress(
    *,
    bus: queue.Queue[tuple[str, Any]],
    stream_factory: Callable[[], Iterator[Any]],
) -> None:
    """Worker target: push parent chunks / errors onto ``bus``, then ``done``."""
    try:
        for item in stream_factory():
            bus.put((_PARENT, item))
    except Exception as exc:  # noqa: BLE001
        bus.put((_ERROR, exc))
    finally:
        bus.put((_DONE, None))


def attach_progress_handler(
    config: dict[str, Any], bus: queue.Queue[tuple[str, Any]]
) -> tuple[dict[str, Any], SubagentProgressHandler]:
    """Copy config and attach a progress handler bound to ``bus``."""
    cfg = dict(config)
    handler = SubagentProgressHandler(bus)
    existing = cfg.get("callbacks")
    if existing is None:
        cfg["callbacks"] = [handler]
    elif isinstance(existing, list):
        cfg["callbacks"] = [*existing, handler]
    else:
        cfg["callbacks"] = [existing, handler]
    return cfg, handler
