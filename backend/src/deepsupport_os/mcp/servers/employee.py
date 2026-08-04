"""Employee MCP server (template).

Local stdio:
  uv run python -m deepsupport_os.mcp.servers.employee

Remote-style HTTP (for MCP client tests):
  uv run python -m deepsupport_os.mcp.servers.employee --http
  # listens http://127.0.0.1:8100/mcp
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from deepsupport_os.db import init_db
from deepsupport_os.db.repositories import EmployeeRepo
from deepsupport_os.db.seed import seed_database

init_db()
seed_database(force=False)

mcp = FastMCP("employee-mcp", host="127.0.0.1", port=8100)
_repo = EmployeeRepo()


@mcp.tool()
def get_employee(employee_id: str = "", email: str = "") -> dict:
    """按 employee_id 或 email 查询员工信息。"""
    if email:
        return _repo.get_by_email(email) or {"error": "not_found"}
    if employee_id:
        return _repo.get_by_id(employee_id) or {"error": "not_found"}
    return {"error": "employee_id_or_email_required"}


@mcp.tool()
def get_department(department: str) -> list:
    """按部门名称列出员工。"""
    return _repo.get_department(department)


@mcp.tool()
def get_manager(employee_id: str) -> dict:
    """查询员工的直属经理。"""
    return _repo.get_manager(employee_id) or {"error": "not_found"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Employee MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve streamable HTTP on 127.0.0.1:8100/mcp (remote client path)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
