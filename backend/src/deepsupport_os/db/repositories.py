from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError

from deepsupport_os.db.models import (
    Account,
    AppliedAction,
    Asset,
    AuditLog,
    Case,
    Employee,
    License,
    Policy,
    Ticket,
    get_session_factory,
)


def _emp_dict(e: Employee) -> dict[str, Any]:
    return {
        "employee_id": e.employee_id,
        "name": e.name,
        "email": e.email,
        "department": e.department,
        "role": e.role,
        "manager_id": e.manager_id,
    }


def make_idempotency_key(tool: str, args: dict[str, Any] | None = None) -> str:
    """Stable key for Exactly-Once write ledger entries."""
    payload = json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(f"{tool}:{payload}".encode("utf-8")).hexdigest()[:40]
    return f"{tool}:{digest}"


def lookup_applied_action(idempotency_key: str) -> dict[str, Any] | None:
    Session = get_session_factory()
    with Session() as s:
        row = s.scalar(
            select(AppliedAction).where(AppliedAction.idempotency_key == idempotency_key)
        )
        if not row:
            return None
        try:
            result = json.loads(row.result_json or "{}")
        except json.JSONDecodeError:
            result = {}
        return {
            "idempotency_key": row.idempotency_key,
            "tool": row.tool,
            "thread_id": row.thread_id,
            "task_id": row.task_id,
            "result": result if isinstance(result, dict) else {"raw": result},
        }


def record_applied_action(
    *,
    tool: str,
    args: dict[str, Any],
    result: dict[str, Any],
    task_id: str | None = None,
    thread_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Insert ledger row; on conflict return the existing result (Exactly Once)."""
    key = idempotency_key or make_idempotency_key(tool, args)
    existing = lookup_applied_action(key)
    if existing:
        return existing["result"]

    Session = get_session_factory()
    with Session() as s:
        row = AppliedAction(
            idempotency_key=key,
            tool=tool,
            args_json=json.dumps(args, ensure_ascii=False, default=str),
            thread_id=thread_id,
            task_id=task_id,
            result_json=json.dumps(result, ensure_ascii=False, default=str),
        )
        s.add(row)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            again = lookup_applied_action(key)
            if again:
                return again["result"]
            raise
    return result


class EmployeeRepo:
    def get_by_id(self, employee_id: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            e = s.get(Employee, employee_id)
            return _emp_dict(e) if e else None

    def get_by_email(self, email: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            e = s.scalar(select(Employee).where(Employee.email == email))
            return _emp_dict(e) if e else None

    def get_department(self, department: str) -> list[dict]:
        Session = get_session_factory()
        with Session() as s:
            rows = s.scalars(
                select(Employee).where(Employee.department == department)
            ).all()
            return [_emp_dict(e) for e in rows]

    def get_manager(self, employee_id: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            e = s.get(Employee, employee_id)
            if not e or not e.manager_id:
                return None
            m = s.get(Employee, e.manager_id)
            return _emp_dict(m) if m else None


class AssetRepo:
    def get_device(self, asset_id: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            a = s.get(Asset, asset_id)
            if not a:
                return None
            return {
                "asset_id": a.asset_id,
                "employee_id": a.employee_id,
                "device_type": a.device_type,
                "os_version": a.os_version,
                "office_version": a.office_version,
                "hostname": a.hostname,
            }

    def list_user_devices(self, employee_id: str | None = None, email: str | None = None) -> list[dict]:
        Session = get_session_factory()
        with Session() as s:
            eid = employee_id
            if email and not eid:
                emp = s.scalar(select(Employee).where(Employee.email == email))
                if not emp:
                    return []
                eid = emp.employee_id
            rows = s.scalars(select(Asset).where(Asset.employee_id == eid)).all()
            return [
                {
                    "asset_id": a.asset_id,
                    "employee_id": a.employee_id,
                    "device_type": a.device_type,
                    "os_version": a.os_version,
                    "office_version": a.office_version,
                    "hostname": a.hostname,
                }
                for a in rows
            ]


class AccountRepo:
    def get_account_status(self, email: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            a = s.scalar(select(Account).where(Account.email == email))
            if not a:
                return None
            return {
                "account_id": a.account_id,
                "email": a.email,
                "status": a.status,
                "mfa_status": a.mfa_status,
                "license_type": a.license_type,
                "employee_id": a.employee_id,
            }

    def get_license(self, email: str) -> list[dict]:
        Session = get_session_factory()
        with Session() as s:
            a = s.scalar(select(Account).where(Account.email == email))
            if not a:
                return []
            rows = s.scalars(select(License).where(License.account_id == a.account_id)).all()
            return [
                {
                    "license_id": lic.license_id,
                    "product": lic.product,
                    "status": lic.status,
                    "expire_at": lic.expire_at,
                    "account_id": lic.account_id,
                }
                for lic in rows
            ]

    def request_password_reset(self, email: str) -> dict:
        """Write intent only — actual reset requires HITL approval in harness.

        State-aware: if the account is already active (reset already applied),
        report ``already_applied`` instead of ``pending_approval`` so the agent
        does not re-request the same reset (which caused approval loops).
        """
        Session = get_session_factory()
        with Session() as s:
            a = s.scalar(select(Account).where(Account.email == email))
            if not a:
                return {"ok": False, "error": "account_not_found"}
            if a.status == "active":
                return {
                    "ok": True,
                    "already_applied": True,
                    "action": "password_reset",
                    "email": email,
                    "account_id": a.account_id,
                    "status": "active",
                    "message": "账号已是 active，密码重置已生效，无需重复申请",
                }
            return {
                "ok": True,
                "pending_approval": True,
                "action": "password_reset",
                "email": email,
                "account_id": a.account_id,
                "current_status": a.status,
            }

    def apply_password_reset(self, email: str) -> dict:
        Session = get_session_factory()
        with Session() as s:
            a = s.scalar(select(Account).where(Account.email == email))
            if not a:
                return {"ok": False, "error": "account_not_found"}
            if a.status == "active":
                return {
                    "ok": True,
                    "already_applied": True,
                    "email": email,
                    "status": "active",
                    "message": "password reset already applied",
                }
            a.status = "active"
            s.commit()
            return {"ok": True, "email": email, "status": "active", "message": "password reset applied"}

    def apply_license_change(self, email: str, new_license_type: str) -> dict:
        Session = get_session_factory()
        with Session() as s:
            a = s.scalar(select(Account).where(Account.email == email))
            if not a:
                return {"ok": False, "error": "account_not_found"}
            target = new_license_type or a.license_type
            if a.license_type == target:
                rows = s.scalars(select(License).where(License.account_id == a.account_id)).all()
                all_active = all(lic.status == "active" for lic in rows) if rows else True
                if all_active:
                    return {
                        "ok": True,
                        "already_applied": True,
                        "email": email,
                        "license_type": a.license_type,
                        "message": "license already at target type",
                    }
            a.license_type = target
            rows = s.scalars(select(License).where(License.account_id == a.account_id)).all()
            for lic in rows:
                lic.status = "active"
            s.commit()
            return {
                "ok": True,
                "email": email,
                "license_type": a.license_type,
                "message": "license change applied",
            }


class TicketRepo:
    def create_ticket(self, **fields: Any) -> dict:
        Session = get_session_factory()
        with Session() as s:
            key = (fields.get("idempotency_key") or "").strip() or None
            if key:
                existing = s.scalar(select(Ticket).where(Ticket.idempotency_key == key))
                if existing:
                    out = self._to_dict(existing)
                    out["ok"] = True
                    out["already_exists"] = True
                    return out

            # Prefer UUID suffix to avoid count+1 races under concurrency.
            for _ in range(5):
                tid = f"T{uuid.uuid4().hex[:8].upper()}"
                if s.get(Ticket, tid) is None:
                    break
            else:
                count = s.scalar(select(func.count()).select_from(Ticket)) or 0
                tid = f"T{1000 + int(count) + 1}"

            t = Ticket(
                ticket_id=tid,
                employee_id=fields.get("employee_id"),
                category=fields.get("category", "General"),
                priority=fields.get("priority", "P3"),
                status=fields.get("status", "open"),
                assignee=fields.get("assignee", "IT Help Desk"),
                title=fields["title"],
                description=fields.get("description", ""),
                resolution=None,
                idempotency_key=key,
            )
            s.add(t)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                if key:
                    existing = s.scalar(select(Ticket).where(Ticket.idempotency_key == key))
                    if existing:
                        out = self._to_dict(existing)
                        out["ok"] = True
                        out["already_exists"] = True
                        return out
                raise
            out = self._to_dict(t)
            out["ok"] = True
            return out

    def get_ticket(self, ticket_id: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            t = s.get(Ticket, ticket_id)
            return self._to_dict(t) if t else None

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        key = (idempotency_key or "").strip()
        if not key:
            return None
        Session = get_session_factory()
        with Session() as s:
            t = s.scalar(select(Ticket).where(Ticket.idempotency_key == key))
            return self._to_dict(t) if t else None

    def find_by_employee_and_title(self, employee_id: str, title: str) -> dict | None:
        """Latest ticket matching employee + title (legacy rows without idempotency_key)."""
        emp = (employee_id or "").strip()
        ttl = (title or "").strip()
        if not emp or not ttl:
            return None
        Session = get_session_factory()
        with Session() as s:
            t = s.scalar(
                select(Ticket)
                .where(Ticket.employee_id == emp, Ticket.title == ttl)
                .order_by(desc(Ticket.created_at))
            )
            return self._to_dict(t) if t else None

    def update_ticket(
        self, ticket_id: str, *, allow_terminal: bool = False, **fields: Any
    ) -> dict | None:
        """Update ticket fields.

        Terminal statuses `closed` / `escalated` require allow_terminal=True
        (HITL apply path). Plain tool calls cannot set them directly.
        """
        Session = get_session_factory()
        with Session() as s:
            t = s.get(Ticket, ticket_id)
            if not t:
                return None
            status = fields.get("status")
            if status in {"closed", "escalated"} and not allow_terminal:
                return {
                    "ok": False,
                    "error": "terminal_status_requires_hitl",
                    "hint": "Use close_ticket / escalate_ticket and await approval",
                    "ticket_id": ticket_id,
                    "requested_status": status,
                }
            for k, v in fields.items():
                if hasattr(t, k) and v is not None:
                    setattr(t, k, v)
            s.commit()
            return self._to_dict(t)

    @staticmethod
    def _to_dict(t: Ticket) -> dict:
        return {
            "ticket_id": t.ticket_id,
            "employee_id": t.employee_id,
            "category": t.category,
            "priority": t.priority,
            "status": t.status,
            "assignee": t.assignee,
            "title": t.title,
            "description": t.description,
            "resolution": t.resolution,
            "idempotency_key": t.idempotency_key,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }


class CaseRepo:
    def search_similar_cases(self, query: str, limit: int = 5) -> list[dict]:
        Session = get_session_factory()
        q = f"%{query}%"
        with Session() as s:
            rows = s.scalars(
                select(Case)
                .where(
                    or_(
                        Case.symptom.like(q),
                        Case.root_cause.like(q),
                        Case.solution.like(q),
                        Case.related_product.like(q),
                        Case.tags.like(q),
                    )
                )
                .limit(limit)
            ).all()
            return [
                {
                    "case_id": c.case_id,
                    "symptom": c.symptom,
                    "root_cause": c.root_cause,
                    "solution": c.solution,
                    "related_product": c.related_product,
                    "tags": c.tags,
                }
                for c in rows
            ]


class PolicyRepo:
    def check_action_permission(self, action: str) -> dict | None:
        Session = get_session_factory()
        with Session() as s:
            p = s.scalar(select(Policy).where(Policy.action == action))
            if not p:
                return None
            return {
                "policy_id": p.policy_id,
                "action": p.action,
                "approval_required": p.approval_required,
                "sla_hours": p.sla_hours,
                "description": p.description,
            }

    def get_sla(self, action: str) -> dict | None:
        return self.check_action_permission(action)


def write_audit(
    task_id: str | None = None,
    tool: str = "",
    arguments: Any = None,
    result: Any = None,
    *,
    thread_id: str | None = None,
) -> None:
    from deepsupport_os.harness.runtime_context import get_task_id, get_thread_id

    resolved_task = (task_id or "").strip() or get_task_id("adhoc")
    resolved_thread = (thread_id or "").strip() or get_thread_id()
    Session = get_session_factory()
    with Session() as s:
        s.add(
            AuditLog(
                task_id=resolved_task,
                thread_id=resolved_thread,
                tool=tool,
                arguments=json.dumps(arguments, ensure_ascii=False, default=str),
                result=json.dumps(result, ensure_ascii=False, default=str),
            )
        )
        s.commit()


def list_audit(
    limit: int = 50,
    task_id: str | None = None,
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    Session = get_session_factory()
    with Session() as s:
        stmt = select(AuditLog).order_by(desc(AuditLog.id)).limit(limit)
        if task_id and thread_id:
            stmt = (
                select(AuditLog)
                .where(AuditLog.task_id == task_id, AuditLog.thread_id == thread_id)
                .order_by(desc(AuditLog.id))
                .limit(limit)
            )
        elif task_id:
            stmt = (
                select(AuditLog)
                .where(AuditLog.task_id == task_id)
                .order_by(desc(AuditLog.id))
                .limit(limit)
            )
        elif thread_id:
            stmt = (
                select(AuditLog)
                .where(AuditLog.thread_id == thread_id)
                .order_by(desc(AuditLog.id))
                .limit(limit)
            )
        rows = s.scalars(stmt).all()
        return [
            {
                "id": r.id,
                "task_id": r.task_id,
                "thread_id": r.thread_id,
                "tool": r.tool,
                "arguments": r.arguments,
                "result": (r.result or "")[:1000],
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in reversed(rows)
        ]
