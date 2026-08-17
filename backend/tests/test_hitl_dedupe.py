"""HITL pending-write dedupe / create+escalate coherence."""

from __future__ import annotations

from unittest.mock import patch

from deepsupport_os.harness.hitl_apply import (
    collect_pending_writes,
    normalize_pending_writes,
    write_dedupe_key,
    write_idempotency_key,
)
from deepsupport_os.harness.hitl_runtime import hitl_resume_decisions


def test_dedupes_create_ticket_with_empty_idempotency_key():
    pending = [
        {
            "name": "request_license_change",
            "args": {"email": "min.zhao@contoso.com", "new_license_type": "Microsoft 365 E3"},
        },
        {
            "name": "create_ticket",
            "args": {
                "title": "Office 登录失败：许可证 LIC004 已过期",
                "description": "diag…",
                "category": "License",
                "priority": "P2",
                "employee_id": "E004",
            },
        },
        {
            "name": "create_ticket",
            "args": {
                "title": "Office 登录失败：许可证 LIC004 已过期",
                "description": "diag…",
                "category": "License",
                "priority": "P2",
                "employee_id": "E004",
                "idempotency_key": "",
            },
        },
    ]
    with patch("deepsupport_os.harness.hitl_apply.write_needs_hitl", return_value=True):
        out = collect_pending_writes(pending=pending)
    names = [w["name"] for w in out]
    assert names.count("create_ticket") == 1
    assert names.count("request_license_change") == 1
    assert "idempotency_key" not in out[1]["args"]


def test_create_ticket_idempotency_ignores_description_drift():
    a = {
        "title": "Outlook 登录失败",
        "description": "short",
        "employee_id": "E001",
        "category": "Access",
        "priority": "P2",
    }
    b = {
        "title": "Outlook 登录失败",
        "description": "much longer diagnosis text…",
        "employee_id": "E001",
        "category": "Access",
        "priority": "P3",
    }
    assert write_dedupe_key("create_ticket", a) == write_dedupe_key("create_ticket", b)
    assert write_idempotency_key("create_ticket", a) == write_idempotency_key("create_ticket", b)


def test_drops_create_when_escalate_targets_existing_ticket():
    pending = [
        {
            "name": "escalate_ticket",
            "args": {"ticket_id": "T3081176B", "reason": "need L2"},
        },
        {
            "name": "create_ticket",
            "args": {
                "title": "Outlook 桌面端登录失败",
                "description": "…",
                "employee_id": "E002",
                "category": "Access",
                "priority": "P2",
            },
        },
    ]
    with (
        patch("deepsupport_os.harness.hitl_apply.write_needs_hitl", return_value=True),
        patch(
            "deepsupport_os.harness.hitl_apply._ticket.get_ticket",
            return_value={"ticket_id": "T3081176B", "status": "open"},
        ),
    ):
        out = collect_pending_writes(pending=pending)
    assert [w["name"] for w in out] == ["escalate_ticket"]


def test_normalize_keeps_create_for_resume_alignment():
    pending = [
        {"name": "escalate_ticket", "args": {"ticket_id": "T1", "reason": "x"}},
        {
            "name": "create_ticket",
            "args": {"title": "t", "description": "d", "employee_id": "E1"},
        },
    ]
    raw = normalize_pending_writes(pending=pending)
    assert [w["name"] for w in raw] == ["escalate_ticket", "create_ticket"]


def test_resume_decisions_match_action_request_count():
    action_requests = [
        {"name": "escalate_ticket", "args": {"ticket_id": "T1", "reason": "x"}},
        {
            "name": "create_ticket",
            "args": {"title": "t", "description": "d", "employee_id": "E1"},
        },
    ]
    applied = [
        {
            "tool": "escalate_ticket",
            "args": {"ticket_id": "T1", "reason": "x"},
            "result": {"ok": True, "action": "escalate_ticket"},
        }
    ]
    with patch(
        "deepsupport_os.harness.hitl_apply.write_needs_hitl",
        side_effect=lambda name, _args: name == "escalate_ticket",
    ):
        decisions = hitl_resume_decisions(
            approved=True, action_requests=action_requests, applied=applied
        )
    assert len(decisions) == 2
    assert decisions[0]["type"] == "respond"
    assert decisions[1]["type"] == "respond"
