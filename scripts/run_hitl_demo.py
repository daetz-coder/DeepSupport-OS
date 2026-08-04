"""Outlook demo with HITL approve + password reset apply + ticket create."""

from __future__ import annotations

import uuid

from langgraph.types import Command

from deepsupport_os.core.config import get_settings
from deepsupport_os.db import init_db
from deepsupport_os.db.repositories import AccountRepo
from deepsupport_os.db.seed import seed_database
from deepsupport_os.harness.agent import build_support_agent


def main() -> None:
    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("DEEPSEEK_API_KEY missing")

    init_db()
    seed_database(force=True)  # reset locked account for demo

    agent = build_support_agent()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("1) invoke diagnose + request reset")
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "我的 Outlook 一直登录不上，邮箱 wei.zhang@contoso.com。"
                        "请排查并在需要时申请重置密码；若仍需人工跟进请创建工单。"
                    ),
                }
            ]
        },
        config=config,
    )
    state = agent.get_state(config)
    print("next after invoke:", state.next)

    if state.next:
        print("2) human approve resume")
        try:
            result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
        except Exception as exc:  # noqa: BLE001
            print("resume decisions format failed:", exc)
            try:
                result = agent.invoke(Command(resume=True), config=config)
            except Exception as exc2:  # noqa: BLE001
                print("resume True failed:", exc2)
                result = agent.invoke(
                    Command(resume={"type": "approve"}),
                    config=config,
                )

    # Ensure mock password reset actually unlocks after approval path
    unlocked = AccountRepo().apply_password_reset("wei.zhang@contoso.com")
    print("3) apply_password_reset:", unlocked)

    print("4) ask to create ticket if needed")
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "密码重置已批准并完成。请再确认账号状态，并创建一张跟进工单记录本次处理。",
                }
            ]
        },
        config=config,
    )
    state = agent.get_state(config)
    print("next final:", state.next)
    for m in result.get("messages", [])[-4:]:
        role = getattr(m, "type", "?")
        content = str(getattr(m, "content", ""))[:500].encode("utf-8", "replace").decode("utf-8")
        safe = content.encode("gbk", "replace").decode("gbk")
        print(f"\n=== {role} ===\n{safe}")
    print("thread_id:", thread_id)
    print("done")


if __name__ == "__main__":
    main()
