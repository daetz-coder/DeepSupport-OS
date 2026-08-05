"""Harness builder — assemble Deep Agents from injectable runtime ports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from langchain.agents.middleware import InterruptOnConfig, TodoListMiddleware

from deepagents import create_deep_agent

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.repositories import AccountRepo, TicketRepo
from deepsupport_os.harness.daytona_backend import build_hybrid_backend, run_sandbox_shell
from deepsupport_os.harness.guard_middleware import support_guard_middleware
from deepsupport_os.harness.memory_files import ensure_memory_files, memory_paths_for_thread
from deepsupport_os.harness.prompts import build_system_prompt
from deepsupport_os.harness.skills_registry import skill_source_paths
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.harness.workspace import ensure_thread_workspace
from deepsupport_os.mcp.tools import all_agent_tools

WRITE_TOOL_NAMES = frozenset(
    {"request_password_reset", "request_license_change", "close_ticket", "escalate_ticket"}
)

# Human resume must use reject | respond only (API is Single Executor for writes).
# `approve` remains allowed so interrupt `when=False` auto-approve can still run
# already-applied tools (returns already_applied); API never sends approve.
_HITL_DECISIONS = ["approve", "reject", "respond"]

def _tool_call_args(req: Any) -> dict[str, Any]:
    """Normalize ToolCallRequest.args whether tool_call is a dict or object."""
    tc = getattr(req, "tool_call", None)
    if tc is None and isinstance(req, dict):
        tc = req.get("tool_call")
    if isinstance(tc, dict):
        args = tc.get("args") or {}
    else:
        args = getattr(tc, "args", None) or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return args if isinstance(args, dict) else {}


def _needs_password_reset(req) -> bool:
    try:
        from deepsupport_os.db.repositories import lookup_applied_action, make_idempotency_key

        args = _tool_call_args(req)
        if lookup_applied_action(make_idempotency_key("request_password_reset", args)):
            return False
        email = str(args.get("email") or "")
        account = AccountRepo().get_account_status(email) if email else None
        return not account or account.get("status") != "active"
    except Exception:  # noqa: BLE001 - conservative: interrupt on lookup failure
        return True


def _needs_license_change(req) -> bool:
    try:
        from deepsupport_os.db.repositories import lookup_applied_action, make_idempotency_key

        args = _tool_call_args(req)
        if lookup_applied_action(make_idempotency_key("request_license_change", args)):
            return False
        email = str(args.get("email") or "")
        target = str(args.get("new_license_type") or "")
        account = AccountRepo().get_account_status(email) if email else None
        return not account or account.get("license_type") != target
    except Exception:  # noqa: BLE001
        return True


def _needs_close(req) -> bool:
    try:
        from deepsupport_os.db.repositories import lookup_applied_action, make_idempotency_key

        args = _tool_call_args(req)
        if lookup_applied_action(make_idempotency_key("close_ticket", args)):
            return False
        ticket_id = str(args.get("ticket_id") or "")
        ticket = TicketRepo().get_ticket(ticket_id) if ticket_id else None
        return not ticket or ticket.get("status") != "closed"
    except Exception:  # noqa: BLE001
        return True


def _needs_escalate(req) -> bool:
    try:
        from deepsupport_os.db.repositories import lookup_applied_action, make_idempotency_key

        args = _tool_call_args(req)
        if lookup_applied_action(make_idempotency_key("escalate_ticket", args)):
            return False
        ticket_id = str(args.get("ticket_id") or "")
        ticket = TicketRepo().get_ticket(ticket_id) if ticket_id else None
        return not ticket or ticket.get("status") != "escalated"
    except Exception:  # noqa: BLE001
        return True


def build_interrupt_on() -> dict[str, bool | InterruptOnConfig]:
    """Interrupt-on map with `when` guards: an action that is already applied
    auto-approves instead of interrupting, so a re-issued write after approval
    cannot loop the HITL prompt.

    `respond` lets the API resume with an already-applied result and skip
    re-running the write tool (which previously invited escalate/close loops).
    """
    return {
        "request_password_reset": InterruptOnConfig(
            allowed_decisions=list(_HITL_DECISIONS), when=_needs_password_reset
        ),
        "request_license_change": InterruptOnConfig(
            allowed_decisions=list(_HITL_DECISIONS), when=_needs_license_change
        ),
        "close_ticket": InterruptOnConfig(
            allowed_decisions=list(_HITL_DECISIONS), when=_needs_close
        ),
        "escalate_ticket": InterruptOnConfig(
            allowed_decisions=list(_HITL_DECISIONS), when=_needs_escalate
        ),
    }


INTERRUPT_ON = build_interrupt_on()


@dataclass
class RuntimePorts:
    """Injectable collaborators for create_deep_agent (testable / swappable)."""

    model_factory: Callable[[], Any]
    tools_factory: Callable[[], list[Any]] = field(default=all_agent_tools)
    skills_factory: Callable[[], list[str]] = field(default=skill_source_paths)
    subagents_factory: Callable[[], list[dict]] = field(default=build_mvp_subagents)
    backend_factory: Callable[..., Any] = field(default=build_hybrid_backend)
    checkpointer_factory: Callable[[], Any] | None = None
    interrupt_on: dict[str, bool | InterruptOnConfig] = field(default_factory=lambda: dict(INTERRUPT_ON))
    # None → derive org + per-thread session via memory_paths_for_thread
    memory_paths: list[str] | None = None
    name: str = "deepsupport-os"


class HarnessBuilder:
    """Build a support agent for one thread without bloating call sites."""

    def __init__(self, ports: RuntimePorts):
        self.ports = ports

    def build(
        self,
        *,
        thread_id: str | None = None,
        workspace: Path | None = None,
        checkpointer: Any = None,
        skills: list[str] | None = None,
        backend: Any = None,
        use_daytona: bool = True,
    ):
        settings = get_settings()
        ensure_memory_files(thread_id=thread_id)

        if workspace is not None:
            ws = workspace
        elif thread_id:
            ws = ensure_thread_workspace(thread_id)
        else:
            ws = settings.resolve(settings.workspace_dir)
        ws.mkdir(parents=True, exist_ok=True)

        # skill_source_paths already gates on disk; virtual roots (/skills/…)
        # must NOT be filtered with Path.exists() (false on Windows).
        skills_dirs = skills or self.ports.skills_factory()

        if backend is not None:
            agent_backend = backend
        else:
            agent_backend = self.ports.backend_factory(
                thread_id=thread_id, attach_daytona=use_daytona
            )

        tools = list(self.ports.tools_factory())
        if use_daytona and settings.daytona_enabled:
            tools.append(run_sandbox_shell)

        cp = checkpointer
        if cp is None and self.ports.checkpointer_factory is not None:
            cp = self.ports.checkpointer_factory()

        memory = (
            list(self.ports.memory_paths)
            if self.ports.memory_paths is not None
            else memory_paths_for_thread(thread_id)
        )

        return create_deep_agent(
            model=self.ports.model_factory(),
            tools=tools,
            system_prompt=build_system_prompt(thread_id=thread_id),
            skills=skills_dirs or None,
            memory=memory,
            middleware=[TodoListMiddleware(system_prompt=""), *support_guard_middleware()],
            subagents=self.ports.subagents_factory(),
            interrupt_on=dict(self.ports.interrupt_on),
            checkpointer=cp,
            backend=agent_backend,
            name=self.ports.name,
        )
