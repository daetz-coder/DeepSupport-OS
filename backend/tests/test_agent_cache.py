from deepsupport_os.api.tasks import get_agent, reset_agents


def test_get_agent_is_per_thread():
    reset_agents()
    a1 = get_agent("thread-aaa")
    a2 = get_agent("thread-bbb")
    a1_again = get_agent("thread-aaa")
    assert a1 is a1_again
    assert a1 is not a2
    reset_agents()


def test_purge_thread_checkpoint_calls_delete():
    from deepsupport_os.harness import agent as ag

    class _FakeCP:
        def __init__(self):
            self.deleted = []

        def delete_thread(self, thread_id: str) -> None:
            self.deleted.append(thread_id)

    fake = _FakeCP()
    prev = ag._checkpointer
    ag._checkpointer = fake
    try:
        assert ag.purge_thread_checkpoint("tid-x") is True
        assert fake.deleted == ["tid-x"]
        assert ag.purge_thread_checkpoint("") is False
    finally:
        ag._checkpointer = prev
