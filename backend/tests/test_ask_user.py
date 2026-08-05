"""Unit tests for ask_user interrupt classification and thread aggregation."""

from deepsupport_os.api.trace import extract_interrupt_info
from deepsupport_os.db import task_store
from deepsupport_os.db.models import reset_engine
from deepsupport_os.mcp.tools import ask_user


class _FakeInterrupt:
    def __init__(self, value):
        self.value = value


class _FakeState:
    def __init__(self, *, nxt, interrupts=(), messages=None):
        self.next = nxt
        self.interrupts = interrupts
        self.tasks = ()
        self.values = {"messages": messages or []}


class _FakeAgent:
    def __init__(self, state):
        self._state = state

    def get_state(self, _config):
        return self._state


def test_ask_user_tool_registered():
    assert ask_user.name == "ask_user"


def test_extract_interrupt_ask_type():
    state = _FakeState(
        nxt=("tools",),
        interrupts=(_FakeInterrupt({"type": "ask", "question": "邮箱是？", "context": ""}),),
    )
    info = extract_interrupt_info(_FakeAgent(state), {"configurable": {"thread_id": "t"}})
    assert info is not None
    assert info["type"] == "ask"
    assert info["question"] == "邮箱是？"
    assert info["pending_writes"] == []


def test_extract_interrupt_hitl_type():
    state = _FakeState(nxt=("tools",), interrupts=())
    info = extract_interrupt_info(_FakeAgent(state), {"configurable": {"thread_id": "t"}})
    assert info is not None
    assert info["type"] == "hitl"


def test_list_threads_groups_runs(fresh_db):
    reset_engine()
    task_store.save_task(
        {
            "task_id": "r1",
            "thread_id": "th-a",
            "status": "completed",
            "messages": [{"role": "user", "content": "hello"}],
        }
    )
    task_store.save_task(
        {
            "task_id": "r2",
            "thread_id": "th-a",
            "status": "interrupted",
            "messages": [{"role": "user", "content": "again"}],
        }
    )
    task_store.save_task(
        {
            "task_id": "r3",
            "thread_id": "th-b",
            "status": "completed",
            "messages": [{"role": "user", "content": "other"}],
        }
    )
    threads = task_store.list_threads(limit=10)
    assert len(threads) >= 2
    a = next(t for t in threads if t["thread_id"] == "th-a")
    assert a["run_count"] == 2
    assert a["latest_task_id"] in {"r1", "r2"}


def test_delete_thread_removes_runs(fresh_db):
    reset_engine()
    task_store.save_task(
        {
            "task_id": "d1",
            "thread_id": "th-del",
            "status": "completed",
            "messages": [{"role": "user", "content": "bye"}],
            "metrics": {"duration_ms": 10},
        }
    )
    task_store.save_task(
        {
            "task_id": "d2",
            "thread_id": "th-del",
            "status": "completed",
            "messages": [{"role": "user", "content": "bye"}],
            "metrics": {"duration_ms": 20},
        }
    )
    assert task_store.count_thread_runs("th-del") == 2
    assert task_store.sum_thread_duration_ms("th-del") == 30
    deleted = task_store.delete_thread("th-del")
    assert deleted == 2
    assert task_store.count_thread_runs("th-del") == 0
    assert task_store.list_threads(limit=10) == [] or all(
        t["thread_id"] != "th-del" for t in task_store.list_threads(limit=10)
    )
