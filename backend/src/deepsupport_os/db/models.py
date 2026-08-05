from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from deepsupport_os.core.config import get_settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    manager_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("employees.employee_id"), nullable=True
    )

    manager: Mapped[Employee | None] = relationship(remote_side=[employee_id])
    assets: Mapped[list[Asset]] = relationship(back_populates="employee")
    account: Mapped[Account | None] = relationship(back_populates="employee")


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("employees.employee_id"), nullable=False
    )
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    os_version: Mapped[str] = mapped_column(String(64), nullable=False)
    office_version: Mapped[str] = mapped_column(String(64), nullable=False)
    hostname: Mapped[str] = mapped_column(String(128), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="assets")


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("employees.employee_id"), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # active/locked/disabled
    mfa_status: Mapped[str] = mapped_column(String(32), nullable=False)  # enabled/disabled
    license_type: Mapped[str] = mapped_column(String(64), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="account")
    licenses: Mapped[list[License]] = relationship(back_populates="account")


class License(Base):
    __tablename__ = "licenses"

    license_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("accounts.account_id"), nullable=False
    )
    product: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # active/expired/pending
    expire_at: Mapped[str] = mapped_column(String(32), nullable=False)

    account: Mapped[Account] = relationship(back_populates="licenses")


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional client key so create_ticket retries do not duplicate rows.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class Case(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    symptom: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    related_product: Mapped[str] = mapped_column(String(64), nullable=False)
    tags: Mapped[str] = mapped_column(String(256), default="")


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    action: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    sla_hours: Mapped[int] = mapped_column(Integer, default=24)
    description: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AppliedAction(Base):
    """Idempotency ledger for HITL / write side effects (Exactly Once)."""

    __tablename__ = "applied_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    tool: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    args_json: Mapped[str] = mapped_column(Text, default="{}")
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TaskRecord(Base):
    """Persisted task/thread snapshot for API lookup after restart."""

    __tablename__ = "task_records"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class EvalCase(Base):
    """Benchmark / automated-test case catalog (seeded from full_cases.jsonl)."""

    __tablename__ = "eval_cases"

    case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expect_json: Mapped[str] = mapped_column(Text, default="{}")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String(64), default="mvp_cases")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class EvalRun(Base):
    """One automated eval suite execution with aggregate metrics."""

    __tablename__ = "eval_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # offline|online
    cases_path: Mapped[str] = mapped_column(String(512), default="")
    use_daytona: Mapped[bool] = mapped_column(Boolean, default=False)
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hitl_hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    offload_hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class EvalCaseResult(Base):
    """Per-case result row for an eval run."""

    __tablename__ = "eval_case_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_runs.run_id"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hitl_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    offload_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


_engine = None
_SessionLocal = None


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url
        if db_url.startswith("sqlite:///"):
            path = settings.resolve(db_url.replace("sqlite:///", "", 1))
            path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{path.as_posix()}"
        _engine = create_engine(db_url, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory():
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
