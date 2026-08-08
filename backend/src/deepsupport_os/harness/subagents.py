"""MVP subagents for DeepSupport OS — with explicit I/O contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from deepsupport_os.mcp.tools import (
    ASSET_TOOLS,
    EMPLOYEE_TOOLS,
    get_account_status,
    get_license,
    get_ticket,
    create_ticket,
    update_ticket,
)
from deepsupport_os.rag.knowledge_tools import KNOWLEDGE_TOOLS


# ---- Structured output contracts (native deepagents response_format) ----
# Each subagent emits a validated JSON object the Main Agent can parse for
# eval / artifact writing instead of free text. `error` carries `ERROR:` + 原因.


class KnowledgeResearchOutput(BaseModel):
    """knowledge-research 的结构化输出契约。"""

    points: list[str] = Field(description="3–8 条要点，要点须含来源标题或 case_id")
    sources: list[str] = Field(default_factory=list, description="来源标题或 case_id 列表")
    suggested_file: str = Field(description="建议主 Agent 写入的文件名，通常为 retrieved_docs.md")
    error: str | None = Field(default=None, description="失败时填 `ERROR:` + 原因；成功为 null")


class EnvironmentDiagnosisOutput(BaseModel):
    """environment-diagnosis 的结构化输出契约。"""

    identity: str | None = Field(default=None, description="员工身份：姓名 / 邮箱 / employee_id")
    account_status: str | None = Field(default=None, description="账号状态")
    mfa: str | None = Field(default=None, description="MFA 状态")
    license: str | None = Field(default=None, description="许可证情况")
    device: str | None = Field(default=None, description="设备 OS / Office 激活情况")
    points: list[str] = Field(description="3–8 条要点")
    suggested_file: str = Field(description="建议主 Agent 写入的文件名，通常为 diagnosis.md")
    error: str | None = Field(default=None, description="失败时填 `ERROR:` + 原因；成功为 null")


class TicketOperationsOutput(BaseModel):
    """ticket-operations 的结构化输出契约。"""

    points: list[str] = Field(description="3–8 条要点")
    ticket_id: str | None = Field(default=None, description="创建/更新的工单 id（如涉及）")
    suggested_file: str = Field(description="建议主 Agent 写入的文件名，通常为 ticket_draft.md")
    error: str | None = Field(default=None, description="失败时填 `ERROR:` + 原因；成功为 null")


_CONTRACT_FOOTER = (
    "\n\n输出契约：结果必须落在本子代理的 `response_format` 结构化字段中，用简体中文；"
    "points 填 3–8 条要点；suggested_file 填建议主 Agent 写入的文件名"
    "（retrieved_docs.md / diagnosis.md / ticket_draft.md 之一）；"
    "若失败，error 字段写 `ERROR:` + 原因，不要假装成功。"
)

# Read-only account tools — write intents stay on Main Agent + HITL apply.
_ACCOUNT_READ_TOOLS = [get_account_status, get_license]
# Ticket ops may draft/update non-terminal state; escalate/close are Main-only.
_TICKET_DRAFT_TOOLS = [create_ticket, get_ticket, update_ticket]


def build_mvp_subagents() -> list[dict]:
    """Three MVP subagents by responsibility (not by product).

    Catalog / enable flags live in capability_registry (R3-4); this builder
    supplies callables + prompts, then filters disabled entries.
    """
    from deepsupport_os.harness.capability_registry import filter_subagents

    specs = [
        {
            "name": "knowledge-research",
            "description": (
                "深入检索 Microsoft 365 支持文档与历史案例，返回带来源的故障处理依据。"
                "当需要查文档、FAQ、相似案例时必须委派给此子代理，主 Agent 不要自己堆长检索。"
            ),
            "system_prompt": (
                "你是 Knowledge Research Agent。\n"
                "输入：用户症状 + 可选邮箱/产品。\n"
                "只使用检索类工具（search_docs / get_document / search_cases）。\n"
                "禁止：改账号、关单、重置密码、写无关文件。\n"
                "成功时要点须含来源标题或 case_id；建议主 Agent 写入 retrieved_docs.md。"
                + _CONTRACT_FOOTER
            ),
            "tools": KNOWLEDGE_TOOLS,
            "response_format": KnowledgeResearchOutput,
        },
        {
            "name": "environment-diagnosis",
            "description": (
                "查询员工、账号、设备与许可证环境，输出环境诊断报告。"
                "当需要确认用户身份、设备或账号状态时必须委派给此子代理。"
            ),
            "system_prompt": (
                "你是 Environment Diagnosis Agent。\n"
                "输入：邮箱或 employee_id。\n"
                "查询员工/账号/设备/许可证，输出结构化诊断"
                "（身份、账号状态、MFA、许可证、设备 OS/Office）。\n"
                "禁止：重置密码、改许可证、关单、升级工单；本子代理无写工具。\n"
                "建议主 Agent 写入 diagnosis.md。"
                + _CONTRACT_FOOTER
            ),
            "tools": EMPLOYEE_TOOLS + _ACCOUNT_READ_TOOLS + ASSET_TOOLS,
            "response_format": EnvironmentDiagnosisOutput,
        },
        {
            "name": "ticket-operations",
            "description": (
                "创建、更新工单（非终态）。当诊断完成需要开单或调整优先级/处理人时委派；"
                "不要在未诊断时过早开单。升级/关闭由主 Agent 发起并走 HITL。"
            ),
            "system_prompt": (
                "你是 Ticket Operations Agent。\n"
                "输入：已有诊断摘要 + 用户诉求。\n"
                "根据上下文创建或更新工单；可用 update_ticket 调整 priority（P1–P4）做升降优先级。\n"
                "禁止：调用 escalate_ticket / close_ticket / 密码重置 / 许可证变更"
                "（终态与高风险写由主 Agent + HITL 执行）。\n"
                "建议主 Agent 写入 ticket_draft.md（含 ticket_id）。"
                + _CONTRACT_FOOTER
            ),
            "tools": _TICKET_DRAFT_TOOLS,
            "response_format": TicketOperationsOutput,
        },
    ]
    return filter_subagents(specs)
