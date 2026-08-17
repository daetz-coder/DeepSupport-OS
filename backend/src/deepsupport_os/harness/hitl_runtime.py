"""HITL resume orchestration — Single Executor apply + respond/reject (R3-2)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from fastapi import HTTPException

from deepsupport_os.harness.hitl_apply import (
    actionable_pending_writes,
    normalize_pending_writes,
    resume_decision_for_write,
    write_dedupe_key,
)
from deepsupport_os.harness.runtime_context import run_context
from deepsupport_os.harness.unit_of_work import WriteUnitOfWork
from deepsupport_os.harness.tracing import span


logger = logging.getLogger(__name__)


def hitl_notice_text(interrupt: dict[str, Any] | None, approved: bool) -> str:
    """Human-readable HITL decision, e.g. `已批准写操作：升级工单`."""
    previews = (interrupt or {}).get("pending_preview") or []
    labels = [
        str(p.get("label") or p.get("name"))
        for p in previews
        if p.get("label") or p.get("name")
    ]
    if not labels:
        writes = (interrupt or {}).get("pending_writes") or []
        labels = [str(w.get("name")) for w in writes if w.get("name")]
    if not labels:
        # Avoid empty "已批准写操作" noise (stale / filtered interrupts).
        return ""
    suffix = f"：{'、'.join(labels)}"
    return f"已批准写操作{suffix}" if approved else f"已拒绝写操作{suffix}"


def inject_hitl_notice(agent: Any, config: dict, interrupt: dict[str, Any], approved: bool) -> None:
    """Persist the HITL decision as a SystemMessage in the checkpoint transcript."""
    try:
        from langchain_core.messages import SystemMessage

        text = hitl_notice_text(interrupt, approved)
        if not text:
            return
        agent.update_state(config, {"messages": [SystemMessage(content=text)]})
    except Exception:  # noqa: BLE001
        logger.exception("inject HITL notice into transcript failed")


def hitl_resume_decisions(
    *,
    approved: bool,
    action_requests: list[dict[str, Any]],
    applied: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one decision per LangGraph action_request (order-preserving)."""
    if not action_requests:
        payload = {
            "ok": False,
            "error": "no_pending_writes",
            "hitl": "reject_skipped" if not approved else "apply_skipped",
            "message": (
                "当前无待执行写操作。请勿继续尝试写入；向用户确认并继续。"
                if not approved
                else "人工已批准但无待写操作。请勿再次调用写工具；向用户说明并继续。"
            ),
        }
        return [{"type": "respond", "message": json.dumps(payload, ensure_ascii=False)}]

    applied_by_key: dict[str, dict[str, Any]] = {}
    for item in applied or []:
        name = str(item.get("tool") or item.get("name") or "")
        args = item.get("args") or {}
        if not name:
            continue
        applied_by_key[write_dedupe_key(name, args)] = item

    return [
        resume_decision_for_write(
            str(w.get("name") or ""),
            w.get("args"),
            approved=approved,
            applied_by_key=applied_by_key,
        )
        for w in action_requests
        if w.get("name")
    ]


def prepare_resume(
    body: Any,
    *,
    get_agent: Callable[[str | None], Any],
    extract_interrupt: Callable[[Any, dict], dict[str, Any] | None],
    drop_cached_agent: Callable[[str], None] | None = None,
) -> tuple[Any, list[dict[str, Any]], str, str, Any, dict, dict[str, Any]]:
    """Validate resume → payload, applied, status, itype, agent, config, interrupt_before."""
    tid = body.thread_id
    from deepsupport_os.harness.agent import agent_run_config

    config = agent_run_config(tid)
    agent = get_agent(tid)
    interrupt_before = extract_interrupt(agent, config) or {}
    itype = (body.interrupt_type or interrupt_before.get("type") or "hitl").strip().lower()

    if itype == "hitl":
        if drop_cached_agent is not None:
            drop_cached_agent(tid)
        agent = get_agent(tid)
        interrupt_before = extract_interrupt(agent, config) or interrupt_before

    applied: list[dict[str, Any]] = []
    if itype == "ask":
        answer = (body.answer if body.answer is not None else body.note) or ""
        if not str(answer).strip():
            raise HTTPException(status_code=400, detail="answer required for ask resume")
        resume_payload: Any = str(answer).strip()
        fallback = "completed"
    else:
        # Decisions must match LangGraph action_requests 1:1 (not the filtered UI list).
        action_requests = normalize_pending_writes(
            pending=interrupt_before.get("action_requests")
            or interrupt_before.get("pending_writes")
            or []
        )
        to_apply = actionable_pending_writes(action_requests)
        if body.approved and to_apply:
            with run_context(thread_id=tid, task_id=body.task_id or tid):
                with span("hitl.prepare_resume", interrupt_type="hitl", approved=True):
                    uow = WriteUnitOfWork(
                        approval_id=str(body.task_id or tid),
                        task_id=body.task_id or body.thread_id,
                        thread_id=tid,
                    )
                    applied = uow.run(to_apply)
        resume_payload = {
            "decisions": hitl_resume_decisions(
                approved=body.approved,
                action_requests=action_requests,
                applied=applied,
            )
        }
        fallback = "approved" if body.approved else "rejected"
    return resume_payload, applied, fallback, itype, agent, config, interrupt_before
