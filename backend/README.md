# Backend package root

Kept for Docker `COPY` / packaging (`pyproject.toml` + this README).

## Harness notes

- HITL writes: `harness/hitl_apply.py` (`write_needs_hitl`, semantic idempotency, create vs escalate coherence).
- Tool guards: `harness/guard_middleware.py` (todos, ask_user dedupe, create-while-escalate skip).
- Timeline from persisted steps: `harness/timeline_from_trace.py`.
