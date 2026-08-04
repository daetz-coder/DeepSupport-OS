"""Run Outlook login-failure demo against the local harness (no HTTP server required)."""

from __future__ import annotations

import json
import uuid

from deepsupport_os.core.config import get_settings
from deepsupport_os.db import init_db
from deepsupport_os.db.seed import seed_database
from deepsupport_os.harness.agent import build_support_agent


def main() -> None:
    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("DEEPSEEK_API_KEY missing in .env")

    init_db()
    seed_database(force=False)

    agent = build_support_agent()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    message = (
        "我的 Outlook 一直登录不上。我的邮箱是 wei.zhang@contoso.com，"
        "请按企业支持流程排查，必要时申请重置密码或创建工单。"
    )

    print("thread_id:", thread_id)
    print("invoking...")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )

    messages = result.get("messages", [])
    print(f"messages: {len(messages)}")
    for m in messages[-8:]:
        role = getattr(m, "type", m.__class__.__name__)
        content = getattr(m, "content", str(m))
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)[:800]
        else:
            content = str(content)[:800]
        print(f"\n=== {role} ===\n{content}")

    state = agent.get_state(config)
    print("\nnext:", getattr(state, "next", None))
    print("done")


if __name__ == "__main__":
    main()
