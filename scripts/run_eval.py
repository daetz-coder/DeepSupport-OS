"""Offline/online evaluation for benchmark cases (default: full_cases.jsonl).

Offline mode checks case schema + golden expect fields without calling LLM.
Online mode invokes the harness and scores tool/HITL presence.

--fast: reuse one agent, disable streaming, no HITL interrupts, skip RAGLab HTTP
(local knowledge fallback only), no skills Glob, no Daytona — for throughput.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "benchmark" / "full_cases.jsonl"
if not CASES.exists():
    CASES = ROOT / "data" / "benchmark" / "mvp_cases.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def score_offline(case: dict[str, Any]) -> dict[str, Any]:
    expect = case.get("expect") or {}
    ok = bool(case.get("id") and case.get("question") and isinstance(expect, dict))
    checks = {
        "has_id": bool(case.get("id")),
        "has_question": bool(case.get("question")),
        "has_expect": bool(expect),
        "has_tags": bool(case.get("tags")),
    }
    return {
        "id": case.get("id"),
        "ok": ok and all(checks.values()),
        "mode": "offline",
        "checks": checks,
        "expect_keys": sorted(expect.keys()),
    }


class FastEvalSession:
    """Shared agent + patches for --fast online runs."""

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI
        from langgraph.checkpoint.memory import MemorySaver

        from deepsupport_os.core.config import get_settings
        from deepsupport_os.db import init_db
        from deepsupport_os.db.seed import seed_database
        from deepsupport_os.harness.agent import build_support_agent
        from deepsupport_os.harness.builder import RuntimePorts
        from deepsupport_os.harness.daytona_backend import build_hybrid_backend
        from deepsupport_os.harness.subagents import build_mvp_subagents
        from deepsupport_os.mcp.tools import all_agent_tools
        from deepsupport_os.rag import client as rag_mod

        settings = get_settings()
        if not settings.llm_configured:
            raise RuntimeError("llm_not_configured")

        init_db()
        seed_database(force=False)

        self._rag_mod = rag_mod
        self._orig_search = rag_mod.RAGLabClient.search_docs
        self._orig_get = rag_mod.RAGLabClient.get_document
        self._orig_list = getattr(rag_mod.RAGLabClient, "list_documents", None)

        def _skip_rag(self, *args, **kwargs):  # noqa: ANN001, ARG001
            return {"ok": False, "error": "fast_eval_skip_raglab"}

        rag_mod.RAGLabClient.search_docs = _skip_rag  # type: ignore[method-assign]
        rag_mod.RAGLabClient.get_document = _skip_rag  # type: ignore[method-assign]
        if self._orig_list is not None:
            rag_mod.RAGLabClient.list_documents = _skip_rag  # type: ignore[method-assign]

        def model_factory() -> ChatOpenAI:
            key, base, model = settings.llm_credentials()
            return ChatOpenAI(
                model=model,
                api_key=key or "EMPTY",
                base_url=base,
                temperature=0,
                streaming=False,
                request_timeout=60,
            )

        ports = RuntimePorts(
            model_factory=model_factory,
            tools_factory=all_agent_tools,
            skills_factory=lambda: [],  # avoid Skills Glob 5s timeouts
            subagents_factory=build_mvp_subagents,
            backend_factory=lambda attach_daytona=False: build_hybrid_backend(
                attach_daytona=False
            ),
            checkpointer_factory=None,
            interrupt_on={},  # HITL tools run immediately (no human wait)
            memory_paths=[],
        )
        self._checkpointer = MemorySaver()
        self.agent = build_support_agent(
            thread_id="eval-fast-shared",
            use_daytona=False,
            checkpointer=self._checkpointer,
            skills=[],
            ports=ports,
        )
        self.fast = True

    def close(self) -> None:
        rag_mod = self._rag_mod
        rag_mod.RAGLabClient.search_docs = self._orig_search  # type: ignore[method-assign]
        rag_mod.RAGLabClient.get_document = self._orig_get  # type: ignore[method-assign]
        if self._orig_list is not None:
            rag_mod.RAGLabClient.list_documents = self._orig_list  # type: ignore[method-assign]


def _score_result(
    case: dict[str, Any],
    *,
    result: dict[str, Any],
    workspace_files: list[str],
    elapsed_ms: float,
    use_daytona: bool,
    fast: bool,
) -> dict[str, Any]:
    from deepsupport_os.api.trace import build_trace
    from deepsupport_os.harness.eval_metrics import enrich_ok, score_trace_extras

    msgs = result.get("messages", [])
    trace = build_trace(msgs)
    steps = list(trace.get("steps") or [])
    tool_names = {t.get("name") for t in trace.get("tool_calls") or []}
    for s in steps:
        if s.get("name") and s.get("kind") in {
            "tool_call",
            "subagent_dispatch",
            "context_offload",
        }:
            tool_names.add(s.get("name"))
    expect = case.get("expect") or {}
    required_tools = set(expect.get("tools") or [])
    hitl_tools = set(expect.get("hitl") or [])
    pending = {p.get("name") for p in (trace.get("pending_writes") or [])}
    subagents = [
        s.get("subagent")
        for s in (trace.get("subagent_dispatches") or [])
        if s.get("subagent")
    ]
    skills_seen = sorted(
        {str(s.get("skill_used")) for s in steps if s.get("skill_used")}
        | set(trace.get("skills_used") or [])
    )

    tool_hit = required_tools.issubset(tool_names) if required_tools else True
    hitl_hit = hitl_tools.issubset(tool_names | pending) if hitl_tools else True

    tags = set(case.get("tags") or [])
    expect_offload = bool(expect.get("workspace_files")) or (
        "context-offload" in tags or "long-task" in tags
    )
    offload_hit = True
    if expect_offload:
        required_files = set(expect.get("workspace_files") or [])
        if required_files:
            offload_hit = required_files.issubset(set(workspace_files))
        else:
            offloads = trace.get("context_offloads") or []
            offload_hit = bool(workspace_files) or bool(offloads)

    # Fast mode skips skills Glob → waive skill gate
    case_for_ok = case
    if fast and expect.get("skills"):
        case_for_ok = {
            **case,
            "expect": {k: v for k, v in expect.items() if k != "skills"},
        }

    extras = score_trace_extras(
        case_for_ok,
        tools_seen={str(x) for x in tool_names if x},
        pending={str(x) for x in pending if x},
        subagents=[str(x) for x in subagents if x],
        skills_seen=skills_seen,
        steps=steps,
        tool_hit=tool_hit,
    )
    if fast and expect.get("skills"):
        extras["skill_hit"] = True
        extras["skill_waived_fast"] = True

    base_ok = tool_hit and hitl_hit and offload_hit
    ok = enrich_ok(base_ok, extras, case_for_ok)
    return {
        "id": case.get("id"),
        "ok": ok,
        "mode": "online",
        "elapsed_ms": round(elapsed_ms, 1),
        "workspace_files": workspace_files,
        "use_daytona": use_daytona,
        "fast": fast,
        "tools_seen": sorted(x for x in tool_names if x),
        "pending_writes": sorted(x for x in pending if x),
        "subagents": [x for x in subagents if x],
        "tool_hit": tool_hit,
        "hitl_hit": hitl_hit,
        "offload_hit": offload_hit,
        "expect_offload": expect_offload,
        "expect_hitl": bool(hitl_tools),
        "expect_skills": bool(expect.get("skills")),
        "expect_subagents": bool(expect.get("subagents")),
        "expect_grounding": "grounding" in tags,
        "tags": sorted(tags),
        **extras,
    }


def score_online(
    case: dict[str, Any],
    *,
    use_daytona: bool = False,
    timeout_s: float = 180.0,
    session: FastEvalSession | None = None,
) -> dict[str, Any]:
    from deepsupport_os.core.config import get_settings
    from deepsupport_os.db import init_db
    from deepsupport_os.db.seed import seed_database
    from deepsupport_os.harness.agent import build_support_agent
    from deepsupport_os.harness.workspace import ensure_thread_workspace
    from langgraph.checkpoint.memory import MemorySaver

    settings = get_settings()
    if not settings.llm_configured:
        return {
            "id": case.get("id"),
            "ok": False,
            "error": "llm_not_configured",
            "mode": "online",
        }

    fast = session is not None
    thread_id = str(uuid.uuid4())
    ws = ensure_thread_workspace(thread_id)
    t0 = time.perf_counter()

    if session is not None:
        agent = session.agent
    else:
        init_db()
        seed_database(force=False)
        agent = build_support_agent(
            thread_id=thread_id,
            use_daytona=use_daytona,
            checkpointer=MemorySaver(),
        )

    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 40 if fast else 50,
    }

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(
                agent.invoke,
                {"messages": [{"role": "user", "content": case["question"]}]},
                config,
            )
            try:
                result = fut.result(timeout=timeout_s)
            except FuturesTimeout:
                shutil.rmtree(ws, ignore_errors=True)
                return {
                    "id": case.get("id"),
                    "ok": False,
                    "mode": "online",
                    "error": f"timeout_after_{int(timeout_s)}s",
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "use_daytona": use_daytona,
                    "fast": fast,
                    "tags": list(case.get("tags") or []),
                }
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(ws, ignore_errors=True)
        return {
            "id": case.get("id"),
            "ok": False,
            "mode": "online",
            "error": str(exc),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "use_daytona": use_daytona,
            "fast": fast,
            "tags": list(case.get("tags") or []),
        }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    workspace_files = (
        sorted(p.name for p in ws.rglob("*") if p.is_file()) if ws.exists() else []
    )
    shutil.rmtree(ws, ignore_errors=True)
    if not isinstance(result, dict):
        result = {"messages": []}
    return _score_result(
        case,
        result=result,
        workspace_files=workspace_files,
        elapsed_ms=elapsed_ms,
        use_daytona=use_daytona and not fast,
        fast=fast,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Offline schema check (default)")
    mode.add_argument("--online", action="store_true", help="Online LLM eval + DB persist")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Load enabled cases from eval_cases table (sync from jsonl first if empty)",
    )
    parser.add_argument(
        "--daytona",
        action="store_true",
        help="Attach Daytona as /sandbox/ sidecar (ignored with --fast)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast online: reuse agent, no stream, auto HITL, skip RAGLab/skills Glob",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        nargs="?",
        const=ROOT / "data" / "benchmark" / "last_eval.json",
        default=None,
        help="Resume online eval: skip finished cases; re-run balance/timeout failures",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=0.0,
        help="Per-case timeout seconds (default: 60 with --fast, else 180)",
    )
    args = parser.parse_args()
    if args.timeout_s <= 0:
        args.timeout_s = 60.0 if args.fast else 180.0
    if args.fast and not args.online:
        raise SystemExit("--fast requires --online")

    if args.from_db:
        from deepsupport_os.db.eval_store import list_eval_cases, sync_eval_cases

        sync_eval_cases(path=args.cases)
        cases = list_eval_cases(enabled_only=True, limit=1000)
    else:
        cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]

    def _needs_rerun(row: dict[str, Any]) -> bool:
        err = str(row.get("error") or "")
        return (
            "Insufficient Balance" in err
            or "402" in err
            or err.startswith("timeout_after_")
        )

    def _write_checkpoint(merged_rows: list[dict[str, Any]]) -> None:
        ck = ROOT / "data" / "benchmark" / "last_eval.resume_partial.json"
        payload = {
            "mode": "online",
            "partial": True,
            "fast": bool(args.fast),
            "total": len(merged_rows),
            "passed": sum(1 for r in merged_rows if r.get("ok")),
            "failed": sum(1 for r in merged_rows if not r.get("ok")),
            "results": merged_rows,
        }
        ck.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    prior_by_id: dict[str, dict[str, Any]] = {}
    resume_ids: set[str] | None = None
    if args.resume is not None:
        resume_path = args.resume
        partial_path = ROOT / "data" / "benchmark" / "last_eval.resume_partial.json"
        if resume_path.name == "last_eval.json" and partial_path.exists():
            if resume_path.exists():
                base = json.loads(resume_path.read_text(encoding="utf-8"))
                for row in base.get("results") or []:
                    cid = str(row.get("id") or "")
                    if cid:
                        prior_by_id[cid] = row
            prior = json.loads(partial_path.read_text(encoding="utf-8"))
            print(f"resume overlay partial {partial_path}", flush=True)
        else:
            if not resume_path.exists():
                raise SystemExit(f"--resume file not found: {resume_path}")
            prior = json.loads(resume_path.read_text(encoding="utf-8"))
        for row in prior.get("results") or []:
            cid = str(row.get("id") or "")
            if cid:
                prior_by_id[cid] = row
        resume_ids = set()
        for cid, row in prior_by_id.items():
            if _needs_rerun(row):
                resume_ids.add(cid)
        for case in cases:
            cid = str(case.get("id") or "")
            if cid and cid not in prior_by_id:
                resume_ids.add(cid)
        keep_n = len([c for c in prior_by_id if c not in resume_ids])
        print(
            f"resume from {resume_path}: keep={keep_n} rerun={len(resume_ids)} "
            f"fast={bool(args.fast)} timeout_s={args.timeout_s}",
            flush=True,
        )

    mode_online = args.online
    results: list[dict[str, Any]] = []
    case_ids_order = [str(c.get("id") or "") for c in cases]
    pending = [
        c for c in cases if resume_ids is None or str(c.get("id") or "") in resume_ids
    ]
    total_n = len(pending) if resume_ids is not None else len(cases)
    done_n = 0
    new_by_id: dict[str, dict[str, Any]] = {}

    session: FastEvalSession | None = None
    if mode_online and args.fast:
        print("building shared --fast agent (no stream / no HITL interrupt / no RAGLab / no skills)...", flush=True)
        t_build = time.perf_counter()
        session = FastEvalSession()
        print(f"fast agent ready in {round((time.perf_counter() - t_build) * 1000)} ms", flush=True)

    try:
        for case in pending if resume_ids is not None else cases:
            done_n += 1
            cid = str(case.get("id") or f"case-{done_n}")
            if mode_online:
                print(f"[{done_n}/{total_n}] online {cid} ...", flush=True)
                t_case = time.perf_counter()
                try:
                    row = score_online(
                        case,
                        use_daytona=False if args.fast else args.daytona,
                        timeout_s=args.timeout_s,
                        session=session,
                    )
                except Exception as exc:  # noqa: BLE001
                    row = {
                        "id": case.get("id"),
                        "ok": False,
                        "mode": "online",
                        "error": str(exc),
                        "use_daytona": args.daytona,
                        "fast": bool(args.fast),
                        "tags": list(case.get("tags") or []),
                    }
                elapsed = round((time.perf_counter() - t_case) * 1000, 1)
                mark = "OK" if row.get("ok") else "FAIL"
                err = f" err={row.get('error')}" if row.get("error") else ""
                print(f"[{done_n}/{total_n}] {mark} {cid} ({elapsed} ms){err}", flush=True)
                new_by_id[cid] = row
                if resume_ids is not None:
                    merged_map = dict(prior_by_id)
                    merged_map.update(new_by_id)
                    merged_rows = [
                        merged_map[oid] for oid in case_ids_order if oid in merged_map
                    ]
                    _write_checkpoint(merged_rows)
            else:
                row = score_offline(case)
                row["tags"] = list(case.get("tags") or [])
                new_by_id[cid] = row
    finally:
        if session is not None:
            session.close()

    if resume_ids is not None:
        for cid in case_ids_order:
            if cid in new_by_id:
                results.append(new_by_id[cid])
            elif cid in prior_by_id:
                kept = dict(prior_by_id[cid])
                kept["resumed_kept"] = True
                results.append(kept)
        for cid, row in new_by_id.items():
            if cid not in case_ids_order:
                results.append(row)
    else:
        results = [
            new_by_id[str(c.get("id") or "")]
            for c in cases
            if str(c.get("id") or "") in new_by_id
        ]

    from deepsupport_os.harness.eval_metrics import aggregate_summary

    summary = aggregate_summary(
        results,
        mode="online" if mode_online else "offline",
        use_daytona=bool(args.daytona) if mode_online and not args.fast else False,
    )
    summary["fast"] = bool(args.fast)
    out = ROOT / "data" / "benchmark" / "last_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    run_id = None
    try:
        from deepsupport_os.db.eval_store import save_eval_run, sync_eval_cases

        synced = sync_eval_cases(path=args.cases)
        run_id = save_eval_run(summary, cases_path=str(args.cases))
        print(f"db: synced {synced['upserted']} cases, run_id={run_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"db persist skipped: {exc}")

    keys = (
        "total",
        "passed",
        "failed",
        "pass_rate",
        "mode",
        "fast",
        "use_daytona",
        "avg_elapsed_ms",
        "p50_elapsed_ms",
        "p95_elapsed_ms",
        "tool_hit_rate",
        "hitl_hit_rate",
        "offload_hit_rate",
        "skill_hit_rate",
        "subagent_hit_rate",
        "planning_hit_rate",
        "write_safety_rate",
        "grounding_rate",
        "long_task_pass_rate",
        "hitl_case_pass_rate",
        "interrupt_rate",
        "error_rate",
        "avg_tool_calls",
        "avg_step_count",
        "avg_subagent_dispatches",
    )
    payload = {k: summary.get(k) for k in keys}
    if summary.get("by_tag"):
        payload["by_tag"] = summary["by_tag"]
    if run_id:
        payload["run_id"] = run_id
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
