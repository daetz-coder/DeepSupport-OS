"""WriteUnitOfWork — Apply → Audit → notice attributes under one span (R3-5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from deepsupport_os.harness.hitl_apply import apply_approved_writes
from deepsupport_os.harness.tracing import mark_ok, span


@dataclass
class WriteUnitOfWork:
    """Exactly-once HITL apply boundary keyed by approval / task identity."""

    approval_id: str
    task_id: str
    thread_id: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    def run(self, writes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with span(
            "hitl.write_uow",
            approval_id=self.approval_id,
            task_id=self.task_id,
            thread_id=self.thread_id or "",
            write_count=len(writes or []),
        ) as s:
            self.results = apply_approved_writes(
                writes,
                task_id=self.task_id,
                thread_id=self.thread_id,
            )
            self.failed = [
                r
                for r in self.results
                if not (isinstance(r.get("result"), dict) and r["result"].get("ok"))
            ]
            ok = not self.failed
            mark_ok(s, ok)
            if s is not None:
                try:
                    s.set_attribute("ds.applied_count", len(self.results))
                    s.set_attribute("ds.failed_count", len(self.failed))
                    if self.failed:
                        # Partial apply: ledger already idempotent; flag for ops.
                        s.set_attribute("ds.compensation_needed", True)
                except Exception:  # noqa: BLE001
                    pass
            return self.results
