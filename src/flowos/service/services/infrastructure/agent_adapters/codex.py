"""Codex adapter — OpenAI Codex CLI integracija.

Codex CLI je agentski alat za kod generisanje i izmene.
Adapter prati isti capability ugovor kao Claude Code adapter.
"""

import os

from flowos.service.services.infrastructure.agent_adapters.claude_code import (
    AdapterCapabilities,
    AgentRequest,
)


class CodexAdapter:
    """Adapter za OpenAI Codex CLI alat.

    Komanda: codex [--model MODEL] [task description]
    Environment: OPENAI_API_KEY iz okruženja.
    """

    AGENT_TYPE = "codex"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            can_launch=True,
            can_stream_events=False,
            can_report_usage=False,
            can_cancel=True,
            can_use_worktree=True,
        )

    def get_command(self, request: AgentRequest) -> list[str]:
        cmd = ["codex"]

        if request.model_name:
            cmd.extend(["--model", request.model_name])

        if request.worktree_path:
            cmd.extend(["--workdir", request.worktree_path])
        elif request.working_directory:
            cmd.extend(["--workdir", request.working_directory])

        if request.task_description:
            cmd.append(request.task_description)

        cmd.extend(request.extra_args)
        return cmd

    def get_environment(self, request: AgentRequest) -> dict[str, str]:
        safe_keys = {
            "PATH",
            "HOME",
            "USER",
            "USERNAME",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "LANG",
            "TERM",
        }
        env = {}
        for key, value in os.environ.items():
            if key in safe_keys or key.startswith("OPENAI_"):
                env[key] = value
        for key, value in request.env.items():
            env[key] = value
        return env
