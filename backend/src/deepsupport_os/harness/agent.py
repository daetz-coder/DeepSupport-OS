"""Deep Agents Harness factory for IT support tasks."""

from __future__ import annotations

import atexit
import sqlite3
from pathlib import Path

from langchain.agents.middleware import TodoListMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from deepagents import create_deep_agent

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.artifacts import CANONICAL_ARTIFACTS
from deepsupport_os.harness.daytona_backend import build_hybrid_backend, run_sandbox_shell
from deepsupport_os.harness.skills_registry import skill_source_paths
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.harness.workspace import ensure_thread_workspace
from deepsupport_os.mcp.tools import all_agent_tools

MEMORY_FILE = "/memory/AGENTS.md"

SYSTEM_PROMPT = """你是 DeepSupport OS，企业 Microsoft 365 IT 技术支持智能体。

工作原则：
1. 先收集用户邮箱/设备等上下文，再查询 Employee、Account、Asset。
2. 复杂检索可委派 knowledge-research；环境排查可委派 environment-diagnosis；开单可委派 ticket-operations。
3. 使用 search_docs / search_cases 获取排查依据；长内容必须写入本地工作区文件，消息中只保留摘要与路径（Context offloading）。
4. 使用 write_todos 维护排障计划（pending / in_progress / completed），复杂任务先规划再执行。
5. 标准产物（Artifacts）写入当前工作区，文件名固定为：
   - retrieved_docs.md — 检索摘要与来源
   - diagnosis.md — 环境/账号诊断
   - ticket_draft.md — 工单草稿（如需）
   - final_resolution.md — 最终处理报告
6. Skills、文档检索、工单/账号工具、长报告均在本地执行。
7. 云端 Daytona（/sandbox/ 或 run_sandbox_shell）仅用于简单短命令；禁止放 Skills 或大批量文件。
8. 高风险写操作必须先 check_action_permission，并等待人工审批。
9. 可更新 /memory/AGENTS.md 中的「会话记忆」短条目（脱敏，禁止密码）。
10. Skills 采用渐进披露：先依据 name/description 选择技能；需要细节时再 read_file 读取 SKILL.md 正文与 references/。
11. 所有结论需有工具结果或文档依据，禁止臆造。

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


def ensure_memory_file() -> Path:
    """Seed repo memory/AGENTS.md used by MemoryMiddleware via LocalShell root."""
    settings = get_settings()
    path = settings.resolve("memory/AGENTS.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# DeepSupport OS Memory\n\n（空模板）\n",
            encoding="utf-8",
        )
    return path


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
    thread_id: str | None = None,
    checkpointer=None,
    skills: list[str] | None = None,
    backend=None,
    use_daytona: bool = True,
):
    settings = get_settings()
    ensure_memory_file()
    if workspace is not None:
        ws = workspace
    elif thread_id:
        ws = ensure_thread_workspace(thread_id)
    else:
        ws = settings.resolve(settings.workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)

    skills_dirs = skills or skill_source_paths()
    existing_skills = [p for p in skills_dirs if Path(p).exists()]

    if backend is not None:
        agent_backend = backend
    else:
        agent_backend = build_hybrid_backend(attach_daytona=use_daytona)

    tools = list(all_agent_tools())
    if use_daytona and settings.daytona_enabled:
        tools.append(run_sandbox_shell)

    prompt = SYSTEM_PROMPT
    if thread_id:
        names = ", ".join(CANONICAL_ARTIFACTS)
        prompt += (
            f"\n\n当前本地工作区：`{ws.as_posix()}`。"
            f"长内容与标准产物（{names}）写入该目录；"
            "云端仅 `/sandbox/` 短小试跑。"
            "Skills 细节在 `skills/*/references/`，按需 read_file。"
        )

    return create_deep_agent(
        model=build_model(),
        tools=tools,
        system_prompt=prompt,
        skills=existing_skills or None,
        memory=[MEMORY_FILE],
        # Deep Agents 默认栈不含 Todo；显式接入并裁剪冗长默认 prompt
        middleware=[TodoListMiddleware(system_prompt="")],
        subagents=build_mvp_subagents(),
        interrupt_on=INTERRUPT_ON,
        checkpointer=checkpointer or get_checkpointer(),
        backend=agent_backend,
        name="deepsupport-os",
    )
