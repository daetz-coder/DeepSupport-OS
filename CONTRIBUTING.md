# Contributing

## Dev setup

See root [README.md](./README.md). Use `.env.example` → `.env` (never commit secrets).

## Skills

- Prefer progressive disclosure: short `SKILL.md` + `references/` for L3 detail
- Tool names in SOPs must match `mcp/tools.py` or remote MCP tool names
- Public skills: add to `skills/catalog.json`, import via `scripts/import_skill.py`

## MCP

- Default: in-process LangChain mock tools (`MCP_LOCAL_TOOLS=true`)
- Remote: edit `config/mcp_servers.json`, set `MCP_REMOTE_ENABLED=true`, run Employee HTTP MCP or your own URL
- Smoke: `scripts/test_remote_mcp.py`

## Tests

```bash
cd backend
uv run pytest -q
```

No CI is configured by project choice; run tests locally before push.

## Docs & screenshots

- Architecture / API / demo: `docs/`
- Optional UI captures: `docs/demo-screenshots/`
