"""Deep Agents Harness factory for IT support tasks."""

from __future__ import annotations

from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent

from deepsupport_os.core.config import get_settings
from deepsupport_os.mcp.tools import all_agent_tools

SYSTEM_PROMPT = """你是 DeepSupport OS，企业 Microsoft 365 IT 技术支持智能体。

工作原则：
1. 先收集用户邮箱/设备等上下文，再查询 Employee、Account、Asset。
2. 使用 search_docs / search_cases 获取排查依据，长内容写入工作区文件。
3. 高风险写操作（密码重置、许可证变更、关闭/升级工单）必须先 check_action_permission，并等待人工审批。
4. 无法自动解决时创建完整工单，并生成结构化处理报告。
5. 所有结论需有工具结果或文档依据，禁止臆造。
"""

# HITL interrupt on write-like tools
INTERRUPT_ON = {
    "request_password_reset": True,
    "request_license_change": True,
    "close_ticket": True,
    "escalate_ticket": True,
}


def build_model() -> ChatOpenAI:
    settings = get_settings()
    api_key, base_url, model = settings.llm_credentials()
    return ChatOpenAI(
        model=model,
        api_key=api_key or "EMPTY",
        base_url=base_url,
        temperature=0,
    )


def build_support_agent(
    *,
    workspace: Path | None = None,
    checkpointer=None,
    skills: list[str] | None = None,
):
    settings = get_settings()
    ws = workspace or settings.resolve(settings.workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)

    skills_dirs = skills or [str(settings.resolve("skills"))]
    existing_skills = [p for p in skills_dirs if Path(p).exists()]

    return create_deep_agent(
        model=build_model(),
        tools=all_agent_tools(),
        system_prompt=SYSTEM_PROMPT,
        skills=existing_skills or None,
        interrupt_on=INTERRUPT_ON,
        checkpointer=checkpointer or MemorySaver(),
        name="deepsupport-os",
    )
