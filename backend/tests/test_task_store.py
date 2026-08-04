from deepsupport_os.db import task_store


def test_task_store_roundtrip(fresh_db):
    record = {
        "task_id": "t-1",
        "thread_id": "th-1",
        "status": "completed",
        "messages": [{"role": "human", "content": "hello"}],
        "trace": {"steps": []},
        "interrupt": None,
        "applied_writes": [],
    }
    task_store.save_task(record)
    loaded = task_store.get_task("t-1")
    assert loaded is not None
    assert loaded["thread_id"] == "th-1"
    by_thread = task_store.get_by_thread("th-1")
    assert by_thread["task_id"] == "t-1"
    items = task_store.list_tasks()
    assert any(i["task_id"] == "t-1" for i in items)
