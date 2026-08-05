"""Deep Agents Harness factory for IT support tasks."""

from __future__ import annotations

import atexit
import sqlite3

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.builder import INTERRUPT_ON, HarnessBuilder, RuntimePorts
from deepsupport_os.harness.memory_files import (
    MEMORY_PATHS,
    ORG_MEMORY_FILE,
    SESSION_MEMORY_FILE,
    ensure_memory_file,
    ensure_memory_files,
    memory_paths_for_thread,
    session_memory_virtual,
)
from deepsupport_os.harness.prompts import SYSTEM_PROMPT, build_system_prompt

# Re-exports for API / tests
# INTERRUPT_ON (InterruptOnConfig with `when` guards) is defined in builder.py.
MEMORY_FILE = SESSION_MEMORY_FILE

_checkpointer: SqliteSaver | MemorySaver | None = None
_sqlite_conn: sqlite3.Connection | None = None


def build_model() -> ChatOpenAI:
    settings = get_settings()
    api_key, base_url, model = settings.llm_credentials()
    return ChatOpenAI(
        model=model,
        api_key=api_key or "EMPTY",
        base_url=base_url,
        temperature=0,
        streaming=True,
    )


def _close_checkpointer() -> None:
    global _checkpointer, _sqlite_conn
    if _sqlite_conn is not None:
        try:
            _sqlite_conn.close()
        except Exception:  # noqa: BLE001
            pass
    _sqlite_conn = None
    _checkpointer = None


def get_checkpointer():
    """SQLite checkpointer with explicit connection lifecycle."""
    global _checkpointer, _sqlite_conn
    if _checkpointer is not None:
        return _checkpointer
    settings = get_settings()
    path = settings.resolve("data/checkpoints.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _sqlite_conn = sqlite3.connect(str(path), check_same_thread=False)
        _checkpointer = SqliteSaver(_sqlite_conn)
        atexit.register(_close_checkpointer)
        return _checkpointer
    except Exception:  # noqa: BLE001
        _checkpointer = MemorySaver()
        return _checkpointer


def purge_thread_checkpoint(thread_id: str) -> bool:
    """Delete LangGraph checkpoints for a thread (best-effort)."""
    tid = (thread_id or "").strip()
    if not tid:
        return False
    cp = get_checkpointer()
    delete = getattr(cp, "delete_thread", None)
    if not callable(delete):
        return False
    try:
        delete(tid)
        return True
    except TypeError:
        # Some savers expect a config dict
        try:
            delete({"configurable": {"thread_id": tid}})
            return True
        except Exception:  # noqa: BLE001
            return False
    except Exception:  # noqa: BLE001
        return False


def default_ports() -> RuntimePorts:
    return RuntimePorts(
        model_factory=build_model,
        checkpointer_factory=get_checkpointer,
        interrupt_on=dict(INTERRUPT_ON),
        # memory_paths=None → per-thread org + session in HarnessBuilder
    )


def build_support_agent(
    *,
    workspace=None,
    thread_id: str | None = None,
    checkpointer=None,
    skills: list[str] | None = None,
    backend=None,
    use_daytona: bool = True,
    ports: RuntimePorts | None = None,
):
    """Assemble support agent via HarnessBuilder (ports injectable for tests)."""
    builder = HarnessBuilder(ports or default_ports())
    return builder.build(
        thread_id=thread_id,
        workspace=workspace,
        checkpointer=checkpointer,
        skills=skills,
        backend=backend,
        use_daytona=use_daytona,
    )


__all__ = [
    "MEMORY_FILE",
    "MEMORY_PATHS",
    "ORG_MEMORY_FILE",
    "SESSION_MEMORY_FILE",
    "SYSTEM_PROMPT",
    "INTERRUPT_ON",
    "build_model",
    "build_support_agent",
    "build_system_prompt",
    "default_ports",
    "ensure_memory_file",
    "ensure_memory_files",
    "get_checkpointer",
    "memory_paths_for_thread",
    "purge_thread_checkpoint",
    "session_memory_virtual",
]
