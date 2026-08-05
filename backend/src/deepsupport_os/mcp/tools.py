"""Mock MCP tool layer — business tools backed by SQLite repositories.

Agent 侧通过 LangChain tools 调用；可选 FastMCP server 对外暴露同一套能力。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from deepsupport_os.db.repositories import (
    AccountRepo,
    AssetRepo,
    CaseRepo,
    EmployeeRepo,
    PolicyRepo,
    TicketRepo,
    write_audit,
)

_employee = EmployeeRepo()
_asset = AssetRepo()
_account = AccountRepo()
_ticket = TicketRepo()
_case = CaseRepo()
_policy = PolicyRepo()


def _audit(tool_name: str, args: dict[str, Any], result: Any, task_id: str = "adhoc") -> Any:
    write_audit(task_id, tool_name, args, result)
    return result


# ---- Employee MCP (template) -------------------------------------------------


@tool
def get_employee(employee_id: str = "", email: str = "") -> dict:
    """按 employee_id 或 email 查询员工信息。"""
    args = {"employee_id": employee_id, "email": email}
    if email:
        result = _employee.get_by_email(email)
    elif employee_id:
        result = _employee.get_by_id(employee_id)
    else:
        result = {"error": "employee_id_or_email_required"}
    return _audit("get_employee", args, result or {"error": "not_found"})


@tool
def get_department(department: str) -> list:
    """按部门名称列出员工。"""
    result = _employee.get_department(department)
    return _audit("get_department", {"department": department}, result)


@tool
def get_manager(employee_id: str) -> dict:
    """查询员工的直属经理。"""
    result = _employee.get_manager(employee_id)
    return _audit("get_manager", {"employee_id": employee_id}, result or {"error": "not_found"})


# ---- Asset -------------------------------------------------------------------


@tool
def get_device(asset_id: str) -> dict:
    """按资产 ID 查询设备信息。"""
    result = _asset.get_device(asset_id)
    return _audit("get_device", {"asset_id": asset_id}, result or {"error": "not_found"})


@tool
def list_user_devices(employee_id: str = "", email: str = "") -> list:
    """列出用户名下设备。可传 employee_id 或 email。"""
    result = _asset.list_user_devices(employee_id=employee_id or None, email=email or None)
    return _audit("list_user_devices", {"employee_id": employee_id, "email": email}, result)


# ---- Account -----------------------------------------------------------------


@tool
def get_account_status(email: str) -> dict:
    """查询 Microsoft 365 账号状态（含 MFA、许可证类型）。"""
    result = _account.get_account_status(email)
    return _audit("get_account_status", {"email": email}, result or {"error": "not_found"})


@tool
def get_license(email: str) -> list:
    """查询账号关联的许可证列表。"""
    result = _account.get_license(email)
    return _audit("get_license", {"email": email}, result)


@tool
def request_password_reset(email: str) -> dict:
    """发起密码重置申请。高风险写操作，通常需要人工审批后才会真正生效。"""
    result = _account.request_password_reset(email)
    return _audit("request_password_reset", {"email": email}, result)


@tool
def request_license_change(email: str, new_license_type: str) -> dict:
    """发起许可证变更申请（需审批）。"""
    result = {
        "ok": True,
        "pending_approval": True,
        "action": "license_change",
        "email": email,
        "new_license_type": new_license_type,
    }
    return _audit("request_license_change", {"email": email, "new_license_type": new_license_type}, result)


# ---- Ticket ------------------------------------------------------------------


@tool
def create_ticket(
    title: str,
    description: str,
    category: str = "General",
    priority: str = "P3",
    employee_id: str = "",
) -> dict:
    """创建 IT 支持工单。"""
    result = _ticket.create_ticket(
        title=title,
        description=description,
        category=category,
        priority=priority,
        employee_id=employee_id or None,
    )
    return _audit(
        "create_ticket",
        {
            "title": title,
            "category": category,
            "priority": priority,
            "employee_id": employee_id,
        },
        result,
    )


@tool
def get_ticket(ticket_id: str) -> dict:
    """查询工单详情。"""
    result = _ticket.get_ticket(ticket_id)
    return _audit("get_ticket", {"ticket_id": ticket_id}, result or {"error": "not_found"})


@tool
def update_ticket(ticket_id: str, status: str = "", resolution: str = "", assignee: str = "") -> dict:
    """更新工单状态、处理人或解决方案。

    不可直接设为 closed/escalated；关闭请用 close_ticket，升级请用 escalate_ticket（需审批）。
    """
    if status in {"closed", "escalated"}:
        result = {
            "ok": False,
            "error": "terminal_status_requires_hitl",
            "hint": "Use close_ticket or escalate_ticket (HITL required)",
        }
        return _audit("update_ticket", {"ticket_id": ticket_id, "status": status}, result)
    fields = {}
    if status:
        fields["status"] = status
    if resolution:
        fields["resolution"] = resolution
    if assignee:
        fields["assignee"] = assignee
    result = _ticket.update_ticket(ticket_id, **fields)
    return _audit("update_ticket", {"ticket_id": ticket_id, **fields}, result or {"error": "not_found"})


@tool
def escalate_ticket(ticket_id: str, reason: str) -> dict:
    """升级工单（通常需要审批；批准后才会真正写入）。"""
    out = {
        "ok": True,
        "pending_approval": True,
        "action": "escalate_ticket",
        "ticket_id": ticket_id,
        "reason": reason,
    }
    return _audit("escalate_ticket", {"ticket_id": ticket_id, "reason": reason}, out)


@tool
def close_ticket(ticket_id: str, resolution: str) -> dict:
    """关闭工单（通常需要审批）。"""
    result = {
        "ok": True,
        "pending_approval": True,
        "action": "close_ticket",
        "ticket_id": ticket_id,
        "resolution": resolution,
    }
    return _audit("close_ticket", {"ticket_id": ticket_id, "resolution": resolution}, result)


# ---- Case / Policy -----------------------------------------------------------


@tool
def search_similar_cases(query: str, limit: int = 5) -> list:
    """检索相似历史故障案例。"""
    result = _case.search_similar_cases(query, limit=limit)
    return _audit("search_similar_cases", {"query": query, "limit": limit}, result)


@tool
def check_action_permission(action: str) -> dict:
    """检查企业策略：某动作是否需要审批及 SLA。"""
    result = _policy.check_action_permission(action)
    return _audit(
        "check_action_permission",
        {"action": action},
        result or {"error": "policy_not_found"},
    )


@tool
def notify_user(email: str, message: str) -> dict:
    """向用户发送通知（Mock）。"""
    result = {"ok": True, "channel": "email", "to": email, "message": message}
    return _audit("notify_user", {"email": email, "message": message}, result)


@tool
def ask_user(question: str, context: str = "") -> str:
    """向用户提问并等待回答。

    仅当对话里确实缺少邮箱、设备或症状细节时调用；禁止臆造。
    若用户已在消息或上一次 ask_user 回答中提供了对应信息，不要再次调用。
    调用后图会中断；用户回答经 resume 注入后作为本工具返回值，必须当作上下文继续执行。
    """
    from langgraph.types import interrupt

    answer = interrupt(
        {
            "type": "ask",
            "question": (question or "").strip() or "请补充信息",
            "context": (context or "").strip(),
        }
    )
    if answer is None:
        return ""
    if isinstance(answer, dict):
        return str(answer.get("answer") or answer.get("text") or answer)
    return str(answer)


EMPLOYEE_TOOLS = [get_employee, get_department, get_manager]
ASSET_TOOLS = [get_device, list_user_devices]
ACCOUNT_TOOLS = [get_account_status, get_license, request_password_reset, request_license_change]
TICKET_TOOLS = [create_ticket, get_ticket, update_ticket, escalate_ticket, close_ticket]
CASE_TOOLS = [search_similar_cases]
POLICY_TOOLS = [check_action_permission]
NOTIFICATION_TOOLS = [notify_user]
DIALOGUE_TOOLS = [ask_user]

ALL_MOCK_TOOLS = (
    EMPLOYEE_TOOLS
    + ASSET_TOOLS
    + ACCOUNT_TOOLS
    + TICKET_TOOLS
    + CASE_TOOLS
    + POLICY_TOOLS
    + NOTIFICATION_TOOLS
    + DIALOGUE_TOOLS
)


def all_agent_tools():
    """Combine in-process mock tools + knowledge + optional remote MCP tools."""
    from deepsupport_os.core.extensions import ext_bool
    from deepsupport_os.harness.tool_provenance import clear_tool_provenance, tag_tool
    from deepsupport_os.rag.knowledge_tools import KNOWLEDGE_TOOLS

    clear_tool_provenance()
    tools: list = []
    if ext_bool("mcp_local_tools"):
        for t in ALL_MOCK_TOOLS:
            tools.append(tag_tool(t, source="local"))
    for t in KNOWLEDGE_TOOLS:
        tools.append(tag_tool(t, source="knowledge"))

    if ext_bool("mcp_remote_enabled"):
        from deepsupport_os.mcp.remote_client import load_remote_mcp_tools

        existing = {getattr(t, "name", "") for t in tools}
        for t in load_remote_mcp_tools():
            name = getattr(t, "name", "")
            if name and name not in existing:
                # Prefer server hint from tool metadata when present
                server = getattr(t, "_ds_server", None) or getattr(t, "metadata", {})
                if isinstance(server, dict):
                    server = server.get("server") or server.get("mcp_server")
                tools.append(tag_tool(t, source="remote", server=str(server) if server else "remote"))
                existing.add(name)
    return tools
