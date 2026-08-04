"""Deep Agents Harness factory for IT support tasks."""

from __future__ import annotations

import atexit
import sqlite3
from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from deepagents import create_deep_agent

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.daytona_backend import get_or_create_daytona_backend
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.mcp.tools import all_agent_tools

SYSTEM_PROMPT = """你是 DeepSupport OS，企业 Microsoft 365 IT 技术支持智能体。

工作原则：
1. 先收集用户邮箱/设备等上下文，再查询 Employee、Account、Asset。
2. 复杂检索可委派 knowledge-research；环境排查可委派 environment-diagnosis；开单可委派 ticket-operations。
3. 使用 search_docs / search_cases 获取排查依据，长内容写入工作区文件（Daytona 沙箱或本地 workspace）。
4. 高风险写操作（密码重置、许可证变更、关闭/升级工单）必须先 check_action_permission，并等待人工审批。
5. 无法自动解决时创建完整工单，并生成结构化处理报告。
6. 所有结论需有工具结果或文档依据，禁止臆造。

演示账号提示：张伟 wei.zhang@contoso.com 账号状态为 locked，适合 Outlook 登录失败场景。
"""

INTERRUPT_ON = {
    "request_password_reset": True,
    "request_license_change": True,
    "close_ticket": True,
    "escalate_ticket": True,
}

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


def build_support_agent(
    *,
    workspace: Path | None = None,
    checkpointer=None,
    skills: list[str] | None = None,
    backend=None,
):
    settings = get_settings()
    ws = workspace or settings.resolve(settings.workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)

    skills_dirs = skills or [str(settings.resolve("skills"))]
    existing_skills = [p for p in skills_dirs if Path(p).exists()]

    agent_backend = backend if backend is not None else get_or_create_daytona_backend()

    return create_deep_agent(
        model=build_model(),
        tools=all_agent_tools(),
        system_prompt=SYSTEM_PROMPT,
        skills=existing_skills or None,
        subagents=build_mvp_subagents(),
        interrupt_on=INTERRUPT_ON,
        checkpointer=checkpointer or get_checkpointer(),
        backend=agent_backend,
        name="deepsupport-os",
    )
