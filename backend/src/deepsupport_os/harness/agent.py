"""Deep Agents Harness factory for IT support tasks."""

from __future__ import annotations

import atexit
import sqlite3

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    register_harness_profile,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.builder import INTERRUPT_ON, HarnessBuilder, RuntimePorts
from deepsupport_os.harness.memory_files import (
    MEMORY_PATHS,
    ORG_MEMORY_FILE,
    ensure_memory_file,
    ensure_memory_files,
    memory_paths_for_thread,
    session_memory_virtual,
)
from deepsupport_os.harness.prompts import SYSTEM_PROMPT, build_system_prompt

# Re-exports for API / tests
# INTERRUPT_ON (InterruptOnConfig with `when` guards) is defined in builder.py.


def _register_native_harness_profile() -> None:
    """Disable the auto-added general-purpose subagent for the harness model.

    `build_model` always returns a ``langchain_openai.ChatOpenAI`` (deepseek or
    ollama via OpenAI-compatible endpoints), whose ``_get_ls_params`` provider
    resolves to "openai", so the provider-level key covers both. With GP off,
    the `task` tool still lists the three purpose-built MVP subagents.
    """
    register_harness_profile(
        "openai",
        HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)),
    )


_register_native_harness_profile()

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
        # Concurrency hardening: FastAPI serves agents from a thread pool, so the
        # shared connection sees concurrent checkpoint writes. WAL + busy_timeout
        # turn "database is locked" into bounded waits instead of hard failures;
        # timeout=30 covers the block while a peer transaction commits.
        _sqlite_conn = sqlite3.connect(
            str(path), check_same_thread=False, timeout=30
        )
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
        _sqlite_conn.execute("PRAGMA busy_timeout=30000")
        _sqlite_conn.execute("PRAGMA synchronous=NORMAL")
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
    "MEMORY_PATHS",
    "ORG_MEMORY_FILE",
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
