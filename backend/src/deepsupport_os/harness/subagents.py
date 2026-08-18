"""MVP subagents for DeepSupport OS — with explicit I/O contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from deepsupport_os.mcp.tools import (
    ASSET_TOOLS,
    EMPLOYEE_TOOLS,
    get_account_status,
    get_license,
    get_ticket,
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
# Ticket ops may update non-terminal state; create/escalate/close are Main+HITL.
_TICKET_DRAFT_TOOLS = [get_ticket, update_ticket]


def _subagent_skill_paths(*names: str) -> list[str]:
    """Enabled builtin skill dirs as virtual /skills/<name>/ roots.

    Attaching skills= to a subagent mounts the progressive-disclosure skill
    index for its role. Missing / disabled skills are filtered out at build time.
    """
    from deepsupport_os.harness.skills_registry import list_skill_dirs

    enabled = {d.name for d in list_skill_dirs(only_enabled=True, include_imported=False)}
    return [f"/skills/{n}/" for n in names if n in enabled]


def build_mvp_subagents() -> list[dict]:
    """Three MVP subagents by responsibility (not by product).

    Catalog / enable flags live in capability_registry (R3-4); this builder
    supplies callables + prompts, then filters disabled entries.
    """
    from deepsupport_os.harness.capability_registry import filter_subagents
    from deepsupport_os.harness.guard_middleware import subagent_budget_middleware

    budget_mw = subagent_budget_middleware()

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
                "优先 `read_file` 相关 `/skills/<name>/SKILL.md`（Outlook/Teams/OneDrive/Office/账号），"
                "再使用检索类工具（search_docs / get_document / search_cases）。\n"
                "禁止：改账号、关单、重置密码、写无关文件。\n"
                "成功时要点须含来源标题或 case_id；建议主 Agent 写入 retrieved_docs.md。\n"
                "工作流：先 search_docs（或 search_cases）一次 → 最多再 get_document 一次关键 doc → 立即输出结构化答案。\n"
                "硬性停止条件：合计业务工具调用不超过 6 次（读 Skill/文件不计入）；"
                "同一 document_id / 同一 query 禁止重复调用；"
                "拿到足够要点后必须停止工具并输出最终结构化答案（middleware 会拦截超额/重复业务工具调用）。"
                + _CONTRACT_FOOTER
            ),
            "tools": KNOWLEDGE_TOOLS,
            "response_format": KnowledgeResearchOutput,
            "middleware": budget_mw,
            "skills": _subagent_skill_paths(
                "outlook-troubleshooting",
                "teams-troubleshooting",
                "onedrive-sync",
                "office-application",
                "account-access",
            ),
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
                "账号/许可证问题先 `read_file` `/skills/account-access/SKILL.md`。\n"
                "禁止：重置密码、改许可证、关单、升级工单；本子代理无写工具。\n"
                "建议主 Agent 写入 diagnosis.md。\n"
                "硬性停止条件：合计业务工具调用不超过 6 次（读 Skill/文件不计入）；"
                "同一参数禁止重复查询；查询完毕后立即输出最终结构化诊断"
                "（middleware 会拦截超额/重复业务工具调用）。"
                + _CONTRACT_FOOTER
            ),
            "tools": EMPLOYEE_TOOLS + _ACCOUNT_READ_TOOLS + ASSET_TOOLS,
            "response_format": EnvironmentDiagnosisOutput,
            "middleware": budget_mw,
            "skills": _subagent_skill_paths("account-access", "office-application"),
        },
        {
            "name": "ticket-operations",
            "description": (
                "查询/更新工单（非终态）。当诊断完成需要调整优先级/处理人时委派；"
                "开单 / 升级 / 关闭由主 Agent 发起并走 HITL。"
            ),
            "system_prompt": (
                "你是 Ticket Operations Agent。\n"
                "输入：已有诊断摘要 + 用户诉求。\n"
                "可查询工单或用 update_ticket 调整 priority（P1–P4）/assignee/非终态 status。\n"
                "禁止：create_ticket / escalate_ticket / close_ticket / 密码重置 / 许可证变更"
                "（开单与终态写由主 Agent + HITL 执行）。\n"
                "建议主 Agent 写入 ticket_draft.md（含建议的 title/description，供主 Agent 开单）。\n"
                "硬性停止条件：合计业务工具调用不超过 6 次（读 Skill/文件不计入）；"
                "同一参数禁止重复操作；操作完成后立即输出最终结构化结果"
                "（middleware 会拦截超额/重复业务工具调用）。"
                + _CONTRACT_FOOTER
            ),
            "tools": _TICKET_DRAFT_TOOLS,
            "response_format": TicketOperationsOutput,
            "middleware": budget_mw,
            "skills": _subagent_skill_paths("ticket-management", "escalation", "resolution-report"),
        },
    ]
    return filter_subagents(specs)
