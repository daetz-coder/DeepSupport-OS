"""Smoke: real HarnessBuilder graph runs via astream (async-only path).

Verifies:
1. agent.astream() executes end-to-end on the event loop (no worker thread).
2. The guard middleware's async `awrap_tool_call` hook actually fires (denies
   get_account_status without todos) — i.e. safety is NOT silently disabled.
3. consume_agent_stream bridges parent chunks / done onto the bus.
"""

import asyncio
import queue
import sys
import traceback

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver

from deepsupport_os.api.subagent_progress import consume_agent_stream
from deepsupport_os.harness.agent import agent_run_config, build_support_agent
from deepsupport_os.harness.builder import RuntimePorts


class StubChatModel(BaseChatModel):
    """Deterministic chat model for async-path smoke tests (real bind_tools)."""

    responses: list

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._next()

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._next()

    def _next(self) -> ChatResult:
        msg = self.responses.pop(0)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "stub"


def fake_model():
    return StubChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_account_status",
                        "args": {"email": "smoke@contoso.com"},
                        "id": "smoke-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="冒烟测试完成", tool_calls=[]),
        ]
    )


async def main() -> None:
    agent = build_support_agent(
        thread_id="smoke-async",
        use_daytona=False,
        ports=RuntimePorts(
            model_factory=fake_model,
            checkpointer_factory=MemorySaver,
        ),
    )
    config = agent_run_config("smoke-async")

    bus: queue.Queue = queue.Queue()
    consumer = asyncio.create_task(
        consume_agent_stream(
            bus=bus,
            agent=agent,
            stream_input={"messages": [{"role": "user", "content": "我的 Outlook 打不开，请诊断"}]},
            stream_config=config,
        )
    )

    kinds: list[str] = []
    parent_modes: set[str] = set()
    errors: list[str] = []
    while True:
        kind, payload = await asyncio.to_thread(bus.get, timeout=20)
        kinds.append(kind)
        if kind == "parent":
            if isinstance(payload, tuple) and len(payload) == 2:
                parent_modes.add(payload[0])
        if kind == "error":
            errors.append(repr(payload))
        if kind == "done":
            break
    await consumer

    print("bus kinds:", kinds)
    print("parent modes:", sorted(parent_modes))
    print("errors:", errors[:3])

    assert kinds[0] == "parent", "expected a parent chunk first"
    assert kinds[-1] == "done", "expected done last"
    assert "updates" in parent_modes, "expected updates stream mode"
    assert not errors, f"agent stream raised: {errors[:1]}"

    # The guard (awrap_tool_call) must have denied get_account_status without todos
    # and the run must have completed with the stubbed assistant message.
    state = agent.get_state(config)
    msgs = state.values.get("messages") or []
    denied = [
        m
        for m in msgs
        if getattr(m, "type", None) == "tool"
        and getattr(m, "status", None) == "error"
        and "todos_required" in str(getattr(m, "content", ""))
    ]
    finished = any(
        getattr(m, "type", None) == "ai" and "冒烟测试完成" in str(getattr(m, "content", ""))
        for m in msgs
    )
    print("guard denial messages:", len(denied))
    assert denied, "async guard hook did NOT fire — safety silently disabled!"
    assert finished, "assistant completion message missing"
    print("SMOKE OK")

    # 4. Drive the actual SSE generator from api/tasks.py end-to-end.
    #    (fresh agent — the stub model's responses were consumed above)
    from deepsupport_os.api.tasks import _iter_agent_sse
    from deepsupport_os.harness.metrics import TurnTimer

    agent2 = build_support_agent(
        thread_id="smoke-sse",
        use_daytona=False,
        ports=RuntimePorts(
            model_factory=fake_model,
            checkpointer_factory=MemorySaver,
        ),
    )
    config2 = agent_run_config("smoke-sse")
    frames: list[str] = []
    async for frame in _iter_agent_sse(
        agent=agent2,
        config=config2,
        stream_input={"messages": [{"role": "user", "content": "resume smoke"}]},
        task_id="sse-smoke",
        thread_id="smoke-sse",
        workspace_path=".",
        timer=TurnTimer(),
    ):
        frames.append(frame["event"])
    print("SSE events:", frames)
    assert frames[0] == "status", "SSE must start with status"
    assert frames[-1] == "done", "SSE must end with done"
    assert any(f == "interrupt" for f in frames) or any(f == "tool_start" for f in frames), \
        "expected tool/interrupt events between status and done"
    print("SSE OK")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)