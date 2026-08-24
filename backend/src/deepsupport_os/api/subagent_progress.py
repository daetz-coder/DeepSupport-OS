"""Bridge nested subagent tool activity into the parent SSE stream.

The main agent now runs on the event loop via `agent.astream()`; the `task`
tool's async coroutine drives `subagent.ainvoke()` on the same loop. LangChain
callbacks fire from arbitrary contexts (loop tasks for async runs, executor
threads for sync tools), so we keep the bus as a thread-safe `queue.Queue` and
drain parent chunks / progress events from the SSE generator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Callable
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from deepsupport_os.harness.timeline_tracker import get_timeline_tracker

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
        self._timeline = get_timeline_tracker()
        # Reuse root started by stream_task — do not create a second main_agent.
        self._agent_span_id: str | None = self._timeline._root_span_id
        self._subagent_span_ids: dict[str, str] = {}
        self._open_tool_spans: dict[str, str] = {}

    def _ensure_agent_span(self) -> str | None:
        if self._agent_span_id:
            return self._agent_span_id
        root = self._timeline._root_span_id
        if root:
            self._agent_span_id = root
            return root
        self._agent_span_id = self._timeline.start_span(
            name="main_agent",
            kind="agent",
            parent_id=None,
        )
        return self._agent_span_id

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
                    parent = self._ensure_agent_span()
                    span_id = self._timeline.start_span(
                        name=self._current_subagent,
                        kind="subagent",
                        parent_id=parent,
                        metadata={"args": args},
                    )
                    self._subagent_span_ids[self._current_subagent] = span_id
            # Parent stream already emits subagent_dispatch; skip duplicate SSE.
            return

        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        parent_span_id = (
            self._subagent_span_ids.get(self._current_subagent)
            if self._task_depth > 0
            else self._ensure_agent_span()
        )
        # Always record tools (main + nested) on the timeline tree.
        kind = "skill" if name in {"read_file", "write_file", "edit_file"} and "/skills/" in str(
            (args or {}).get("file_path") or (args or {}).get("path") or input_str or ""
        ) else "tool"
        span_id = self._timeline.start_span(
            name=name,
            kind=kind,
            parent_id=parent_span_id,
            metadata={"args": args if args is not None else input_str},
        )
        self._open_tool_spans[str(run_id)] = span_id

        if not nested:
            # Parent SSE already surfaces main-agent tools; timeline-only here.
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
                span_id = self._subagent_span_ids.get(self._current_subagent)
                if span_id:
                    self._timeline.end_span(span_id, status="completed")
            return

        span_id = self._open_tool_spans.pop(str(run_id), None)
        if span_id:
            self._timeline.end_span(span_id, status="completed")
        else:
            timeline = self._timeline.get_timeline()
            for span in reversed(timeline):
                if span["name"] == resolved and span["kind"] in {"tool", "skill"} and span["end_time"] is None:
                    self._timeline.end_span(span["id"], status="completed")
                    break

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
        name = str(kwargs.get("name") or "tool")
        span_id = self._open_tool_spans.pop(str(run_id), None)
        if span_id:
            self._timeline.end_span(span_id, status="failed", metadata={"error": str(error)})
        else:
            timeline = self._timeline.get_timeline()
            for span in reversed(timeline):
                if (
                    span["name"] == name
                    and span["kind"] in {"tool", "skill"}
                    and span["end_time"] is None
                ):
                    self._timeline.end_span(
                        span["id"], status="failed", metadata={"error": str(error)}
                    )
                    break

        nested = self._task_depth > 0 or _is_subagent_meta(metadata, tags)
        if not nested:
            return

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
        self._ensure_agent_span()

        if not nested:
            return

        # Start LLM timeline span (subagent only — avoids flooding main LLM nodes)
        parent_span_id = (
            self._subagent_span_ids.get(self._current_subagent)
            if self._task_depth > 0
            else self._agent_span_id
        )
        self._timeline.start_span(
            name="llm_call",
            kind="llm",
            parent_id=parent_span_id,
        )

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
        
        # End LLM timeline span
        timeline = self._timeline.get_timeline()
        for span in reversed(timeline):
            if span["kind"] == "llm" and span["end_time"] is None:
                self._timeline.end_span(span["id"], status="completed")
                break
        
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
        
        # End LLM timeline span with error status
        timeline = self._timeline.get_timeline()
        for span in reversed(timeline):
            if span["kind"] == "llm" and span["end_time"] is None:
                self._timeline.end_span(span["id"], status="failed", metadata={"error": str(error)})
                break
        
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


async def consume_agent_stream(
    *,
    bus: queue.Queue[tuple[str, Any]],
    agent: Any,
    stream_input: Any,
    stream_config: dict[str, Any],
) -> None:
    """Async consumer: push `agent.astream()` chunks / errors onto ``bus``.

    Runs as a task on the event loop; parent items are enqueued as they are
    produced so the SSE generator can interleave them with progress events.
    """
    timeline = get_timeline_tracker()
    try:
        async for item in agent.astream(
            stream_input,
            config=stream_config,
            stream_mode=["updates", "messages"],
        ):
            bus.put((_PARENT, item))
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        bus.put((_ERROR, exc))
    finally:
        # End main agent timeline span
        if timeline._root_span_id:
            timeline.end_span(timeline._root_span_id, status="completed")
        try:
            bus.put((_DONE, None))
        except asyncio.CancelledError:
            raise


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
