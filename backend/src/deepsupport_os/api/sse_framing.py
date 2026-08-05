"""SSE event framing helpers (R3-3): monotonic seq + run_id on every payload."""

from __future__ import annotations

import json
from typing import Any, Iterator


class SseSequencer:
    """Assign causal sequence numbers within one agent run/stream."""

    def __init__(self, *, run_id: str, thread_id: str):
        self.run_id = run_id
        self.thread_id = thread_id
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    @property
    def seq(self) -> int:
        return self._seq

    def event(self, event: str, data: Any) -> dict[str, str]:
        """Build an SSE frame; dict payloads gain seq/run_id/thread_id."""
        if isinstance(data, dict):
            payload = {
                "seq": self.next_seq(),
                "run_id": self.run_id,
                "thread_id": self.thread_id,
                **data,
            }
            body = json.dumps(payload, ensure_ascii=False, default=str)
        else:
            # Non-dict (rare): wrap so clients always see seq.
            payload = {
                "seq": self.next_seq(),
                "run_id": self.run_id,
                "thread_id": self.thread_id,
                "value": data,
            }
            body = json.dumps(payload, ensure_ascii=False, default=str)
        return {"event": event, "data": body}


def iter_with_seq(
    events: Iterator[dict[str, str]],
    *,
    run_id: str,
    thread_id: str,
) -> Iterator[dict[str, str]]:
    """Re-frame raw {event,data} dicts that already JSON-encoded data without seq.

    Prefer SseSequencer.event at the source; this is a fallback wrapper.
    """
    seq = SseSequencer(run_id=run_id, thread_id=thread_id)
    for frame in events:
        event = frame.get("event") or "message"
        raw = frame.get("data") or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}
        if not isinstance(data, dict):
            data = {"value": data}
        # Avoid double-wrapping if already sequenced
        if "seq" in data and "run_id" in data:
            yield frame
        else:
            yield seq.event(event, data)
