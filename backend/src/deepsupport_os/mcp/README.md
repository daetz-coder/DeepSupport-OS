# `mcp/`

工具双轨：本地 LangChain `@tool` 适配 Mock DB；可选远程 MCP。详见 `docs/adr/0001-mcp-dual-track.md`。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 包标记（无导出） |
| `tools.py` | Local Tool Adapter：员工/账号/资产/工单/策略/HITL 写意图等；`ALL_MOCK_TOOLS`、`main_agent_tools` |
| `remote_client.py` | 远程 MCP：`load_remote_mcp_tools`、服务器配置 CRUD、启停与缓存重置 |
| [`servers/`](./servers/) | 可选独立 FastMCP 进程模板（非默认挂载路径） |

## 工具归属

- **读**：`get_employee`、`get_account_status`、`get_license`、`list_user_devices`、`get_ticket`…
- **写（多需 HITL）**：`request_password_reset`、`request_license_change`、`escalate_ticket`、`close_ticket`…
- **工单**：`create_ticket`、`update_ticket`（部分经 ticket 子代理）
- **知识工具**在 `rag/knowledge_tools.py`，构建时与本地工具合并
