"""HITL decision notice text (persisted into the transcript on resume)."""

from __future__ import annotations

import json

from deepsupport_os.api.tasks import _hitl_notice_text, _hitl_resume_decisions


def test_hitl_notice_text():
    interrupt = {
        "pending_preview": [
            {"name": "escalate_ticket", "label": "升级工单"},
            {"name": "close_ticket", "label": "关闭工单"},
        ]
    }
    assert _hitl_notice_text(interrupt, True) == "已批准写操作：升级工单、关闭工单"
    assert _hitl_notice_text(interrupt, False) == "已拒绝写操作：升级工单、关闭工单"
    assert _hitl_notice_text(None, True) == "已批准写操作"
    assert _hitl_notice_text({"pending_writes": [{"name": "escalate_ticket"}]}, True) == (
        "已批准写操作：escalate_ticket"
    )


def test_hitl_resume_uses_respond_after_successful_apply():
    pending = [{"name": "escalate_ticket", "args": {"ticket_id": "T1012", "reason": "x"}}]
    applied = [
        {
            "tool": "escalate_ticket",
            "args": pending[0]["args"],
            "result": {"ok": True, "action": "escalate_ticket", "ticket": {"status": "escalated"}},
        }
    ]
    decisions = _hitl_resume_decisions(approved=True, pending=pending, applied=applied)
    assert len(decisions) == 1
    assert decisions[0]["type"] == "respond"
    payload = json.loads(decisions[0]["message"])
    assert payload["ok"] is True
    assert payload["hitl"] == "approved_and_applied"


def test_hitl_resume_reject_and_approve_fallback():
    pending = [{"name": "escalate_ticket", "args": {"ticket_id": "T1"}}]
    rejected = _hitl_resume_decisions(approved=False, pending=pending, applied=[])
    assert rejected[0]["type"] == "reject"
    # apply failed / empty → fall back to approve (tool runs)
    approve = _hitl_resume_decisions(approved=True, pending=pending, applied=[])
    assert approve[0]["type"] == "approve"
