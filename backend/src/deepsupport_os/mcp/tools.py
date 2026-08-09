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


def _audit(tool_name: str, args: dict[str, Any], result: Any, task_id: str | None = None) -> Any:
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
    """发起许可证变更申请（需审批）。已生效时返回 already_applied，避免重复审批。"""
    account = _account.get_account_status(email)
    if account and account.get("license_type") == new_license_type:
        result = {
            "ok": True,
            "already_applied": True,
            "action": "license_change",
            "email": email,
            "new_license_type": new_license_type,
            "status": "active",
            "message": "许可证已是目标类型，无需重复变更",
        }
    else:
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
    idempotency_key: str = "",
) -> dict:
    """创建 IT 支持工单。传入 idempotency_key 可避免重复开单。"""
    result = _ticket.create_ticket(
        title=title,
        description=description,
        category=category,
        priority=priority,
        employee_id=employee_id or None,
        idempotency_key=idempotency_key or None,
    )
    return _audit(
        "create_ticket",
        {
            "title": title,
            "category": category,
            "priority": priority,
            "employee_id": employee_id,
            "idempotency_key": idempotency_key,
        },
        result,
    )


@tool
def get_ticket(ticket_id: str) -> dict:
    """查询工单详情。"""
    result = _ticket.get_ticket(ticket_id)
    return _audit("get_ticket", {"ticket_id": ticket_id}, result or {"error": "not_found"})


# Non-terminal ticket statuses allowed via update_ticket (no HITL).
_TICKET_STATUSES = frozenset({"open", "in_progress", "pending", "resolved"})
_TICKET_PRIORITIES = frozenset({"P1", "P2", "P3", "P4"})


@tool
def update_ticket(
    ticket_id: str,
    status: str = "",
    resolution: str = "",
    assignee: str = "",
    priority: str = "",
) -> dict:
    """更新工单：状态 / 优先级 / 处理人 / 解决方案。

    - status 仅允许：open / in_progress / pending / resolved（不可写 P1–P4）
    - priority 仅允许：P1 / P2 / P3 / P4（降级或调优优先级用此字段，不要塞进 status）
    - 不可直接设为 closed/escalated；关闭用 close_ticket，升级用 escalate_ticket（需审批）
    """
    if status in {"closed", "escalated"}:
        result = {
            "ok": False,
            "error": "terminal_status_requires_hitl",
            "hint": "Use close_ticket or escalate_ticket (HITL required)",
        }
        return _audit("update_ticket", {"ticket_id": ticket_id, "status": status}, result)

    if status and status not in _TICKET_STATUSES:
        result = {
            "ok": False,
            "error": "invalid_status",
            "allowed_status": sorted(_TICKET_STATUSES),
            "hint": "priority 请用 priority 参数（P1–P4），不要写入 status",
            "requested_status": status,
        }
        return _audit("update_ticket", {"ticket_id": ticket_id, "status": status}, result)

    if priority and priority not in _TICKET_PRIORITIES:
        result = {
            "ok": False,
            "error": "invalid_priority",
            "allowed_priority": sorted(_TICKET_PRIORITIES),
            "requested_priority": priority,
        }
        return _audit("update_ticket", {"ticket_id": ticket_id, "priority": priority}, result)

    fields: dict = {}
    if status:
        fields["status"] = status
    if resolution:
        fields["resolution"] = resolution
    if assignee:
        fields["assignee"] = assignee
    if priority:
        fields["priority"] = priority
    if not fields:
        result = {
            "ok": False,
            "error": "no_fields",
            "hint": "Provide at least one of status / priority / resolution / assignee",
        }
        return _audit("update_ticket", {"ticket_id": ticket_id}, result)

    updated = _ticket.update_ticket(ticket_id, **fields)
    if not updated:
        result = {"ok": False, "error": "not_found", "ticket_id": ticket_id}
    elif isinstance(updated, dict) and updated.get("error"):
        result = updated
    else:
        result = {"ok": True, "ticket": updated, "updated_fields": sorted(fields.keys())}
    return _audit("update_ticket", {"ticket_id": ticket_id, **fields}, result)


def _ticket_state(ticket_id: str) -> dict | None:
    """Read current ticket state (None when missing)."""
    return _ticket.get_ticket(ticket_id)


@tool
def escalate_ticket(ticket_id: str, reason: str) -> dict:
    """升级工单（通常需要审批；批准后才会真正写入）。已升级时返回 already_applied，避免重复审批。"""
    ticket = _ticket_state(ticket_id)
    if ticket and ticket.get("status") == "escalated":
        result = {
            "ok": True,
            "already_applied": True,
            "action": "escalate_ticket",
            "ticket_id": ticket_id,
            "status": "escalated",
            "message": "工单已升级，无需重复升级",
        }
    else:
        result = {
            "ok": True,
            "pending_approval": True,
            "action": "escalate_ticket",
            "ticket_id": ticket_id,
            "reason": reason,
        }
    return _audit("escalate_ticket", {"ticket_id": ticket_id, "reason": reason}, result)


@tool
def close_ticket(ticket_id: str, resolution: str) -> dict:
    """关闭工单（通常需要审批）。已关闭时返回 already_applied，避免重复审批。"""
    ticket = _ticket_state(ticket_id)
    if ticket and ticket.get("status") == "closed":
        result = {
            "ok": True,
            "already_applied": True,
            "action": "close_ticket",
            "ticket_id": ticket_id,
            "status": "closed",
            "message": "工单已关闭，无需重复关闭",
        }
    else:
        result = {
            "ok": True,
            "pending_approval": True,
            "action": "close_ticket",
            "ticket_id": ticket_id,
            "resolution": resolution,
        }
    return _audit("close_ticket", {"ticket_id": ticket_id, "resolution": resolution}, result)


# ---- Case / Policy -----------------------------------------------------------

# Canonical Policy.action values for the HITL write tools. `check_action_permission`
# accepts either the tool name or the canonical action, and the R3-1 guard matches
# on the canonical action so checking a *different* action cannot satisfy it.
POLICY_ACTION_FOR_TOOL: dict[str, str] = {
    "request_password_reset": "password_reset",
    "request_license_change": "license_change",
    "close_ticket": "close_ticket",
    "escalate_ticket": "escalate_ticket",
}


@tool
def search_similar_cases(query: str, limit: int = 5) -> list:
    """检索相似历史故障案例。"""
    result = _case.search_similar_cases(query, limit=limit)
    return _audit("search_similar_cases", {"query": query, "limit": limit}, result)


@tool
def check_action_permission(action: str) -> dict:
    """检查企业策略：某动作是否需要审批及 SLA。

    高风险写操作（request_password_reset / request_license_change /
    close_ticket / escalate_ticket）前必须调用；传工具名或策略动作名均可。
    """
    resolved = POLICY_ACTION_FOR_TOOL.get(action, action)
    result = _policy.check_action_permission(resolved)
    return _audit(
        "check_action_permission",
        {"action": resolved},
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
    from deepsupport_os.harness.capability_registry import filter_tools
    from deepsupport_os.harness.tool_provenance import tag_tool
    from deepsupport_os.rag.knowledge_tools import KNOWLEDGE_TOOLS

    # Do NOT call clear_tool_provenance() here: each build registers the same
    # tool names and register_tool_provenance overwrites per name, so clearing
    # the shared registry on every build just races concurrent builds of other
    # threads and drops their tags.
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
    return filter_tools(tools)
