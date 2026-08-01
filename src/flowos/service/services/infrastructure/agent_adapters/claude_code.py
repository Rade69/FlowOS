"""Agent adapteri — interfejs i Claude Code implementacija.

Capability model:
- can_launch: FlowOS sme pokrenuti alat
- can_stream_events: alat emituje strukturirane događaje
- can_report_usage: alat prijavljuje tokene/trošak
- can_cancel: podržava kontrolisani prekid
- can_use_worktree: radi ispravno u zadatom worktreeju

Adapter zna: komandu, argumente, environment, kako prepoznaje izlaz.
Core Services ne znaju konkretne CLI detalje pojedinačnog agenta.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


# ═══════════════════════════════════════════════════════════════════
# Capability model
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AdapterCapabilities:
    can_launch: bool = True
    can_stream_events: bool = False
    can_report_usage: bool = False
    can_cancel: bool = True
    can_use_worktree: bool = True


# ═══════════════════════════════════════════════════════════════════
# Agent Request / Result
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentRequest:
    """Zahtev za pokretanje agenta."""

    agent_type: str
    working_directory: str
    repo_path: str
    model_name: str | None = None
    task_description: str | None = None
    branch_name: str | None = None
    worktree_path: str | None = None
    extra_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Rezultat agentske sesije."""

    exit_code: int
    stdout_summary: str  # poslednjih N linija
    stderr_summary: str
    duration_seconds: float
    interrupted: bool = False


# ═══════════════════════════════════════════════════════════════════
# Adapter Protocol
# ═══════════════════════════════════════════════════════════════════


class AgentAdapter(Protocol):
    """Ugovor za agentski adapter."""

    def capabilities(self) -> AdapterCapabilities: ...

    def get_command(self, request: AgentRequest) -> list[str]: ...

    def get_environment(self, request: AgentRequest) -> dict[str, str]: ...


# ═══════════════════════════════════════════════════════════════════
# Claude Code adapter
# ═══════════════════════════════════════════════════════════════════


class ClaudeCodeAdapter:
    """Adapter za Claude Code CLI alat.

    Komanda: claude [--model MODEL] [--workdir DIR] [task description]

    Environment: filtrira tajne, koristi samo bezbedne varijable.
    """

    AGENT_TYPE = "claude-code"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            can_launch=True,
            can_stream_events=False,  # Claude Code CLI ne emituje structured events
            can_report_usage=False,
            can_cancel=True,
            can_use_worktree=True,
        )

    def get_command(self, request: AgentRequest) -> list[str]:
        cmd = ["claude"]

        if request.model_name:
            cmd.extend(["--model", request.model_name])

        if request.worktree_path:
            cmd.extend(["--workdir", request.worktree_path])
        elif request.working_directory:
            cmd.extend(["--workdir", request.working_directory])

        if request.branch_name:
            cmd.extend(["--branch", request.branch_name])

        if request.task_description:
            cmd.append(request.task_description)

        cmd.extend(request.extra_args)
        return cmd

    def get_environment(self, request: AgentRequest) -> dict[str, str]:
        """Filtrirani environment — bez tajni.

        Zadržava: PATH, HOME, USER, SYSTEMROOT, TEMP, TMP.
        Uklanja: API ključeve, tokene, secrets.
        """
        safe_keys = {"PATH", "HOME", "USER", "USERNAME", "SYSTEMROOT", "TEMP", "TMP", "LANG", "TERM"}
        env = {}
        for key, value in os.environ.items():
            if key in safe_keys or key.startswith("CLAUDE_") or key.startswith("ANTHROPIC_"):
                env[key] = value
        env.update(request.env)
        return env


# ═══════════════════════════════════════════════════════════════════
# Process launcher (koristi Job Object na Windows-u)
# ═══════════════════════════════════════════════════════════════════


class AgentProcessLauncher:
    """Pokreće agentski proces sa Job Object kontrolom."""

    def __init__(self, adapter: AgentAdapter) -> None:
        self._adapter = adapter

    def launch(self, request: AgentRequest, *, timeout: float | None = None) -> AgentResult:
        """Pokreće agenta i čeka rezultat.

        Args:
            request: AgentRequest sa svim parametrima.
            timeout: Timeout u sekundama (None = bez timeout-a).

        Returns:
            AgentResult sa exit_code, stdout i stderr.
        """
        import time

        cmd = self._adapter.get_command(request)
        env = self._adapter.get_environment(request)

        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=request.working_directory,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                interrupted = False
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                interrupted = True

            proc.wait()  # Osiguraj da je returncode dostupan

            duration = time.monotonic() - start

            return AgentResult(
                exit_code=proc.returncode or -1,
                stdout_summary=stdout[-2000:] if stdout else "",
                stderr_summary=stderr[-2000:] if stderr else "",
                duration_seconds=duration,
                interrupted=interrupted,
            )
        except FileNotFoundError:
            return AgentResult(
                exit_code=-1,
                stdout_summary="",
                stderr_summary=f"Komanda nije pronađena: {cmd[0]}",
                duration_seconds=time.monotonic() - start,
                interrupted=False,
            )

    def kill_process_tree(self, pid: int) -> None:
        """Ubija celo stablo procesa koristeći Windows Job Object."""
        if sys.platform == "win32":
            try:
                from ctypes import windll, wintypes

                kernel32 = windll.kernel32
                handle = kernel32.OpenProcess(1, False, pid)
                if handle:
                    kernel32.TerminateProcess(handle, 1)
                    kernel32.CloseHandle(handle)
            except Exception:
                pass