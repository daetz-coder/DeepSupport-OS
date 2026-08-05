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
from deepsupport_os.harness.workspace import ensure_thread_workspace, thread_workspace_virtual
from deepsupport_os.mcp.tools import all_agent_tools

MEMORY_FILE = "/memory/AGENTS.md"

# Role + hard constraints only. SOPs live in Skills; org/demo facts live in memory/AGENTS.md;
# artifact filenames are defined in harness.artifacts (see manifest.json).
SYSTEM_PROMPT = """你是 DeepSupport OS，企业 Microsoft 365 IT 技术支持智能体。

硬约束：
1. 先取用户邮箱/设备上下文，再查员工、账号、资产；结论必须有工具或文档依据，禁止臆造。
2. 复杂检索委派 knowledge-research；环境排查委派 environment-diagnosis；开单/改单委派 ticket-operations。
3. 长内容写入当前工作区虚拟路径（以 `/` 开头），消息只保留摘要与路径；回合结束保持 `manifest.json` 与产物一致。
4. 复杂任务先 `write_todos` 再执行；匹配 Skill 时先看 name/description，细节再 `read_file` `/skills/<name>/SKILL.md`。
5. 高风险写操作先 `check_action_permission`，并等待人工审批；禁止在未批准时声称已改账号/关单。
6. 本地执行 Skills/检索/工单；`/sandbox/` 与 `run_sandbox_shell` 仅短命令。
7. 可向 `/memory/AGENTS.md`「会话记忆」追加脱敏短条目；禁止密码与令牌。
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
        vws = thread_workspace_virtual(thread_id)
        prompt += (
            f"\n\n当前工作区：`{vws}/`（虚拟路径，禁止盘符绝对路径）。"
            f"标准产物见该目录 `manifest.json`（schema 定义：{', '.join(CANONICAL_ARTIFACTS)}）。"
            "Skills：`/skills/<name>/SKILL.md`；沙箱：`/sandbox/`。"
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
