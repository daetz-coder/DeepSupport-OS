"""HITL resume orchestration — Single Executor apply + respond/reject (R3-2)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from fastapi import HTTPException

from deepsupport_os.harness.hitl_apply import collect_pending_writes
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
    suffix = f"：{'、'.join(labels)}" if labels else ""
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
    pending: list[dict[str, Any]],
    applied: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build HITL resume decisions (respond/reject only — never approve)."""
    if not approved:
        if not pending:
            payload = {
                "ok": False,
                "error": "no_pending_writes",
                "hitl": "reject_skipped",
                "message": "用户拒绝了该操作，但当前无待执行写操作。请勿继续尝试写入；向用户确认并继续。",
            }
            return [{"type": "respond", "message": json.dumps(payload, ensure_ascii=False)}]
        reject_msg = (
            "用户拒绝了该写操作。请勿再次调用同一写工具；"
            "改用其它方案，或向用户确认下一步。"
        )
        return [{"type": "reject", "message": reject_msg} for _ in pending]

    if not pending:
        payload = {
            "ok": False,
            "error": "no_pending_writes",
            "hitl": "apply_skipped",
            "message": "人工已批准但无待写操作。请勿再次调用写工具；向用户说明并继续。",
        }
        return [{"type": "respond", "message": json.dumps(payload, ensure_ascii=False)}]

    decisions: list[dict[str, Any]] = []
    for i, w in enumerate(pending):
        if i < len(applied) and isinstance(applied[i].get("result"), dict):
            result = dict(applied[i]["result"])
            if result.get("ok"):
                result.setdefault("hitl", "approved_and_applied")
                result.setdefault(
                    "message",
                    "人工已批准，写操作已落库。勿再次调用同一写工具；继续收尾并回复用户。",
                )
            else:
                result.setdefault("hitl", "approved_but_apply_failed")
                result.setdefault(
                    "message",
                    "人工已批准但落库失败。请勿再次调用同一写工具；向用户说明错误并改用其它方案。",
                )
        else:
            result = {
                "ok": False,
                "error": "apply_missing",
                "hitl": "approved_but_apply_failed",
                "tool": w.get("name"),
                "args": w.get("args") or {},
                "message": (
                    "人工已批准但落库未执行。请勿再次调用同一写工具；"
                    "向用户说明并改用其它方案。"
                ),
            }
        decisions.append(
            {"type": "respond", "message": json.dumps(result, ensure_ascii=False, default=str)}
        )
    return decisions


def prepare_resume(
    body: Any,
    *,
    get_agent: Callable[[str | None], Any],
    extract_interrupt: Callable[[Any, dict], dict[str, Any] | None],
    drop_cached_agent: Callable[[str], None] | None = None,
) -> tuple[Any, list[dict[str, Any]], str, str, Any, dict, dict[str, Any]]:
    """Validate resume → payload, applied, status, itype, agent, config, interrupt_before."""
    tid = body.thread_id
    config = {"configurable": {"thread_id": tid}}
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
        pending = collect_pending_writes(None, pending=interrupt_before.get("pending_writes"))
        if body.approved and pending:
            with run_context(thread_id=tid, task_id=body.task_id or tid):
                with span("hitl.prepare_resume", interrupt_type="hitl", approved=True):
                    uow = WriteUnitOfWork(
                        approval_id=str(body.task_id or tid),
                        task_id=body.task_id or body.thread_id,
                        thread_id=tid,
                    )
                    applied = uow.run(pending)
        resume_payload = {
            "decisions": hitl_resume_decisions(
                approved=body.approved, pending=pending, applied=applied
            )
        }
        fallback = "approved" if body.approved else "rejected"
    return resume_payload, applied, fallback, itype, agent, config, interrupt_before
