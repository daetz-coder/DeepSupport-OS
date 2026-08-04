# Demo Playbook

## Prerequisites

```bash
cp .env.example .env   # set DEEPSEEK_API_KEY
cd backend && uv sync && uv run deepsupport-os
cd frontend && npm install && npm run dev
```

Demo users (seeded):

| Email | Scenario |
|---|---|
| wei.zhang@contoso.com | Outlook login / locked account |
| na.li@contoso.com | Teams audio |
| qiang.wang@contoso.com | OneDrive sync |
| min.zhao@contoso.com | Office activation / license |

## Scripts

```bash
cd backend
uv run python ../scripts/run_outlook_demo.py
uv run python ../scripts/run_hitl_demo.py
uv run python ../scripts/smoke_checkpoint.py
uv run pytest
uv run python ../scripts/run_eval.py --offline   # tool/HITL expectation checks without LLM
```

## UI flow

1. Submit Outlook question with `wei.zhang@contoso.com`
2. Watch SSE / structured tool steps
3. Approve HITL → password unlock applied
4. Ask to create follow-up ticket
