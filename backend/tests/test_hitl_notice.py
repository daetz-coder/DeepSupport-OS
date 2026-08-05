"""HITL decision notice text (persisted into the transcript on resume)."""

from __future__ import annotations

from deepsupport_os.api.tasks import _hitl_notice_text


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
