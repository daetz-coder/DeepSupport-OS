"""MVP subagents for DeepSupport OS."""

from __future__ import annotations

from deepsupport_os.mcp.tools import (
    ACCOUNT_TOOLS,
    ASSET_TOOLS,
    EMPLOYEE_TOOLS,
    TICKET_TOOLS,
)
from deepsupport_os.rag.knowledge_tools import KNOWLEDGE_TOOLS


def build_mvp_subagents() -> list[dict]:
    """Three MVP subagents by responsibility (not by product)."""
    return [
        {
            "name": "knowledge-research",
            "description": (
                "深入检索 Microsoft 365 支持文档与历史案例，返回带来源的故障处理依据。"
                "当需要查文档、FAQ、相似案例时委派给此子代理。"
            ),
            "system_prompt": (
                "你是 Knowledge Research Agent。只负责检索文档与案例，"
                "把关键证据写入简洁报告，标注来源，不要执行写操作。"
            ),
            "tools": KNOWLEDGE_TOOLS,
        },
        {
            "name": "environment-diagnosis",
            "description": (
                "查询员工、账号、设备与许可证环境，输出环境诊断报告。"
                "当需要确认用户身份、设备或账号状态时委派给此子代理。"
            ),
            "system_prompt": (
                "你是 Environment Diagnosis Agent。查询员工/账号/设备/许可证，"
                "输出结构化环境诊断，不要重置密码或改许可证。"
            ),
            "tools": EMPLOYEE_TOOLS + ACCOUNT_TOOLS + ASSET_TOOLS,
        },
        {
            "name": "ticket-operations",
            "description": (
                "创建、更新、升级工单。当诊断完成需要开单或变更工单时委派。"
            ),
            "system_prompt": (
                "你是 Ticket Operations Agent。根据已有诊断上下文创建或更新工单。"
                "升级/关闭前先检查策略；高风险操作保留审批标记。"
            ),
            "tools": TICKET_TOOLS,
        },
    ]
