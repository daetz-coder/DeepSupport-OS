"""Smoke-test remote MCP connectivity (HTTP Employee server).

Terminal A:
  cd backend && uv run python -m deepsupport_os.mcp.servers.employee --http

Terminal B:
  cd backend && uv run python ../../scripts/test_remote_mcp.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from deepsupport_os.core.config import get_settings
from deepsupport_os.mcp.remote_client import (
    build_client_connections,
    load_remote_mcp_tools,
    mcp_status,
    reset_mcp_cache,
)


def main() -> None:
    get_settings.cache_clear()
    # Force remote path for this smoke script
    import os

    os.environ["MCP_REMOTE_ENABLED"] = "true"
    get_settings.cache_clear()
    reset_mcp_cache()

    conns = build_client_connections()
    print("connections:", json.dumps(conns, indent=2, ensure_ascii=False))
    if not conns:
        print("No enabled MCP servers. Edit config/mcp_servers.json")
        sys.exit(1)

    tools = load_remote_mcp_tools(force=True)
    status = mcp_status()
    print("status:", json.dumps(status, indent=2, ensure_ascii=False, default=str))
    print("tools:", [getattr(t, "name", t) for t in tools])
    if status.get("error") or not tools:
        sys.exit(2)
    print("OK")


if __name__ == "__main__":
    main()
