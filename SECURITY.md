# Security

## Secrets

- Put API keys in `.env` only (DeepSeek, Daytona, remote MCP tokens)
- Never commit `.env`, credentials, or production tenant tokens
- `config/mcp_servers.json` may reference remote URLs; keep bearer headers in env, not in git

## Network & admin API

- Local default bind is `API_HOST=127.0.0.1` (not LAN-facing). Docker sets `0.0.0.0` for port mapping.
- Optional `ADMIN_TOKEN`: when set, mutating `/api/meta/*` and `/admin/seed` require header `X-Admin-Token`. Frontend may set `VITE_ADMIN_TOKEN`.
- `/health` is liveness-only; external probes live at `/api/health/deps`.

## Skills & MCP supply chain

- Imported skills can steer agent behavior (prompt injection packaged as folders)
- Catalog downloads are restricted to `https://raw.githubusercontent.com/…`
- Review upstream LICENSE and SKILL.md before `--accept-license` / production use
- Prefer official or high-install sources ([skills.sh](https://skills.sh/), known orgs)
- Remote MCP servers execute tools with the privileges of their credentials — scope narrowly and prefer read-only where possible

## HITL

High-risk writes (`request_password_reset`, `request_license_change`, `close_ticket`, `escalate_ticket`) require human approval before DB apply.

## Reporting

Open a GitHub issue for vulnerabilities; do not file public issues with live secrets.
