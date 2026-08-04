"""Minimal checkpoint resume smoke test (no LLM if thread empty)."""

from __future__ import annotations

import uuid

from deepsupport_os.db import init_db
from deepsupport_os.db.seed import seed_database
from deepsupport_os.harness.agent import build_support_agent


def main() -> None:
    init_db()
    seed_database(force=False)
    agent = build_support_agent()
    thread_id = f"ckpt-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config)
    print("fresh thread next:", state.next)
    print("checkpointer ok")


if __name__ == "__main__":
    main()
