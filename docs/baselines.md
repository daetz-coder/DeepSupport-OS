# Evaluation Baselines

DeepSupport OS compares harness value against lighter stacks.

| Group | Capabilities | Purpose |
|---|---|---|
| Baseline A — RAG Chatbot | `search_docs` only, no write MCP | Show retrieval alone cannot finish IT ops |
| Baseline B — Tool-calling Agent | LLM + tools via `create_agent`, no Skills/Subagents/Daytona FS | Show plain function-calling limits on long tasks |
| Baseline C — Fixed LangGraph | Fixed nodes/branches | Compare static workflow vs dynamic harness (后置) |
| DeepSupport OS Full | Harness + Skills + FS + Subagents + Memory + Checkpoint + HITL | Target system |

## Capability matrix (offline)

```bash
cd backend
uv run python ../scripts/run_baselines.py --offline
```

| Capability | A | B | Full |
|---|---|---|---|
| RAG / search_docs | ✓ | ✓ | ✓ |
| MCP / business tools | ✗ | ✓ | ✓ |
| Skills | ✗ | ✗ | ✓ |
| Subagents | ✗ | ✗ | ✓ |
| HITL apply (password/license/ticket) | ✗ | ✗* | ✓ |
| Filesystem / Daytona workspace | ✗ | ✗ | ✓ |

\* Baseline B may *call* write tools but lacks Deep Agents HITL middleware + apply pipeline used by Full.

## Live comparison (online)

```bash
cd backend
# Full harness (small smoke)
uv run python ../scripts/run_eval.py --online --limit 3
# Baselines A/B
uv run python ../scripts/run_baselines.py --online --limit 3 --profile both
```

Outputs:

- `data/benchmark/last_eval.json` — Full harness scores
- `data/benchmark/last_baselines.json` — A/B scores + capability matrix

## Core metrics

| Metric | Meaning |
|---|---|
| Task Success (`pass_rate`) | Expectation match (required tools + HITL tools present) |
| Tool hit rate | Required tools subset of observed tool calls |
| HITL hit rate | Expected HITL write tools seen / pending |
| Avg elapsed ms | Wall time per case (online) |
| Long-task | Cases tagged `long-task` / multi-tool (compare A fail vs Full) |
| Write Safety | Terminal ticket states only via HITL apply (Full only) |

## Expected qualitative result

| Scenario | A | B | Full |
|---|---|---|---|
| Outlook locked → password reset | RAG snippets only | May call tools; weak planning | Skills + HITL + apply |
| Multi-product long diagnosis | No account/device tools | Tools without Skills/Subagents | Subagents + workspace offload |
| Close/escalate ticket | Cannot | Unsafe / no apply gate | HITL gated apply |

Cases: `data/benchmark/mvp_cases.jsonl` (~30). Offline schema check:

```bash
uv run python ../scripts/run_eval.py --offline
```
