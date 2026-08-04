# Evaluation Baselines

DeepSupport OS compares harness value against lighter stacks. Implementation of A/B/C runners can come later; this doc defines the contract.

| Group | Capabilities | Purpose |
|---|---|---|
| Baseline A — RAG Chatbot | Local/RAGLab retrieval only, no write MCP | Show retrieval alone cannot finish IT ops |
| Baseline B — Tool-calling Agent | LLM + tools, no Skills/Subagents/Filesystem | Show plain function-calling limits on long tasks |
| Baseline C — Fixed LangGraph | Fixed nodes/branches | Compare static workflow vs dynamic harness |
| DeepSupport OS Lite | Planner + MCP + RAG | Measure basic agent skill |
| DeepSupport OS Full | Harness + Skills + FS + Subagents + Memory + Checkpoint + HITL | Target system |

## Core metrics (MVP script)

- Task Success Rate (expectation match)
- Tool Selection / presence of required tools
- HITL triggered when expected
- Write-operation Safety (terminal ticket states only via HITL apply)
- Average completion time (when online LLM eval enabled)

Cases live in `data/benchmark/mvp_cases.jsonl`. Run:

```bash
uv run python scripts/run_eval.py --offline
```
