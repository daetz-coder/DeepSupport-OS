# ADR 0001 — MCP Dual Track (Local Adapter vs Remote MCP)

- **Status**: Accepted (transitional)
- **Date**: 2026-08-05

## Context

DeepSupport OS documents “Mock MCP”, but the default runtime tools are **in-process LangChain `@tool` functions** in `mcp/tools.py` that call SQLite repositories directly. A real FastMCP server exists only for Employee (`mcp/servers/employee.py`) as a remote/HTTP template. Remote MCP loading is optional via `config/mcp_servers.json` + `extensions.json`.

This dual track confuses contributors: “should I add a `@tool` or a FastMCP server?”

## Decision

1. **Name the layers clearly**
   - **Local Tool Adapter**：进程内 LangChain tools（当前默认、低延迟、HITL 友好）。
   - **Remote MCP**：`MultiServerMCPClient` 拉取的外部/同机 HTTP·stdio 服务。

2. **Near term (this repo)**  
   Keep Local Adapter as the source of truth for demo ITSM tools. FastMCP Employee remains the **extension template** for remote-style deployment. Do not silently duplicate every tool into FastMCP until an adapter generator exists.

3. **Convergence path (later)**  
   - Option A：各域 FastMCP 为唯一实现，本地用 stdio/http 挂载进 agent。  
   - Option B：从同一 domain service 生成 `@tool` 与 FastMCP 包装。  
   Prefer Option B for HITL latency; Option A for strict MCP-only demos.

4. **UX**  
   Remote servers default `enabled: false`. When remote load fails, `GET /api/meta/mcp` must surface `runtime.error`（已有），UI should not imply tools merged.

## Consequences

- Docs/README must say “Local Tool Adapter + optional Remote MCP”, not imply all tools are MCP servers.
- New domains: implement Local Adapter first for demo; add FastMCP when remote packaging is needed.
- F-01 HarnessBuilder should inject a `ToolPort` interface so the dual track can swap later without rewriting the factory.
