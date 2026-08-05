"""Harness builder — assemble Deep Agents from injectable runtime ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from langchain.agents.middleware import TodoListMiddleware

from deepagents import create_deep_agent

from deepsupport_os.core.config import get_settings
from deepsupport_os.harness.daytona_backend import build_hybrid_backend, run_sandbox_shell
from deepsupport_os.harness.memory_files import MEMORY_PATHS, ensure_memory_files
from deepsupport_os.harness.prompts import build_system_prompt
from deepsupport_os.harness.skills_registry import skill_source_paths
from deepsupport_os.harness.subagents import build_mvp_subagents
from deepsupport_os.harness.workspace import ensure_thread_workspace
from deepsupport_os.mcp.tools import all_agent_tools

INTERRUPT_ON = {
    "request_password_reset": True,
    "request_license_change": True,
    "close_ticket": True,
    "escalate_ticket": True,
}


@dataclass
class RuntimePorts:
    """Injectable collaborators for create_deep_agent (testable / swappable)."""

    model_factory: Callable[[], Any]
    tools_factory: Callable[[], list[Any]] = field(default=all_agent_tools)
    skills_factory: Callable[[], list[str]] = field(default=skill_source_paths)
    subagents_factory: Callable[[], list[dict]] = field(default=build_mvp_subagents)
    backend_factory: Callable[..., Any] = field(default=build_hybrid_backend)
    checkpointer_factory: Callable[[], Any] | None = None
    interrupt_on: dict[str, bool] = field(default_factory=lambda: dict(INTERRUPT_ON))
    memory_paths: list[str] = field(default_factory=lambda: list(MEMORY_PATHS))
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
        ensure_memory_files()

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
            agent_backend = self.ports.backend_factory(attach_daytona=use_daytona)

        tools = list(self.ports.tools_factory())
        if use_daytona and settings.daytona_enabled:
            tools.append(run_sandbox_shell)

        cp = checkpointer
        if cp is None and self.ports.checkpointer_factory is not None:
            cp = self.ports.checkpointer_factory()

        return create_deep_agent(
            model=self.ports.model_factory(),
            tools=tools,
            system_prompt=build_system_prompt(thread_id=thread_id),
            skills=skills_dirs or None,
            memory=list(self.ports.memory_paths),
            middleware=[TodoListMiddleware(system_prompt="")],
            subagents=self.ports.subagents_factory(),
            interrupt_on=dict(self.ports.interrupt_on),
            checkpointer=cp,
            backend=agent_backend,
            name=self.ports.name,
        )
