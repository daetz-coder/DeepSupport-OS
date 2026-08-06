# `mcp/servers/`

可独立启动的 FastMCP 服务模板。默认运行路径走 `mcp/tools.py` 本地适配；此处用于演示「远程 MCP 进程」形态。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 包标记（无导出） |
| `employee.py` | Employee FastMCP：stdio/HTTP 暴露员工查询类工具，可被 `remote_client` 接入 |
