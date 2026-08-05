"""Request-scoped run identity for tools / audit (AR-11 / R2-5)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_task_id: ContextVar[str | None] = ContextVar("ds_task_id", default=None)
_thread_id: ContextVar[str | None] = ContextVar("ds_thread_id", default=None)


def get_task_id(default: str = "adhoc") -> str:
    return _task_id.get() or default


def get_thread_id() -> str | None:
    return _thread_id.get()


def set_run_context(*, thread_id: str | None = None, task_id: str | None = None) -> tuple:
    """Bind context; returns tokens for reset_run_context."""
    t_thread = _thread_id.set((thread_id or "").strip() or None)
    t_task = _task_id.set((task_id or "").strip() or None)
    return t_thread, t_task


def reset_run_context(tokens: tuple) -> None:
    t_thread, t_task = tokens
    _thread_id.reset(t_thread)
    _task_id.reset(t_task)


@contextmanager
def run_context(*, thread_id: str | None = None, task_id: str | None = None) -> Iterator[None]:
    tokens = set_run_context(thread_id=thread_id, task_id=task_id)
    try:
        yield
    finally:
        reset_run_context(tokens)
