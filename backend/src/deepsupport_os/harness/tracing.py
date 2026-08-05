"""OpenTelemetry helpers with graceful no-op fallback (AR-17 / R3-5)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from deepsupport_os.harness.runtime_context import get_task_id, get_thread_id

_TRACER_NAME = "deepsupport-os"


def _tracer():
    try:
        from opentelemetry import trace

        return trace.get_tracer(_TRACER_NAME)
    except Exception:  # noqa: BLE001 - optional dependency / misconfigured SDK
        return None


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    """Start a span; yields the span object or None when OTel is unavailable."""
    tracer = _tracer()
    if tracer is None:
        yield None
        return

    merged = {
        "ds.task_id": get_task_id(""),
        "ds.thread_id": get_thread_id() or "",
        **{f"ds.{k}" if not str(k).startswith("ds.") else str(k): v for k, v in attrs.items()},
    }
    with tracer.start_as_current_span(name) as s:
        for key, value in merged.items():
            if value is None or value == "":
                continue
            try:
                s.set_attribute(key, value if isinstance(value, (bool, int, float)) else str(value))
            except Exception:  # noqa: BLE001
                pass
        try:
            yield s
        except Exception as exc:
            try:
                s.record_exception(exc)
                s.set_attribute("ds.error", True)
            except Exception:  # noqa: BLE001
                pass
            raise


def mark_ok(s: Any, ok: bool) -> None:
    if s is None:
        return
    try:
        s.set_attribute("ds.ok", bool(ok))
    except Exception:  # noqa: BLE001
        pass
