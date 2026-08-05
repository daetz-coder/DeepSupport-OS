from deepsupport_os.api.tasks import get_agent, reset_agents


def test_get_agent_is_per_thread():
    reset_agents()
    a1 = get_agent("thread-aaa")
    a2 = get_agent("thread-bbb")
    a1_again = get_agent("thread-aaa")
    assert a1 is a1_again
    assert a1 is not a2
    reset_agents()
