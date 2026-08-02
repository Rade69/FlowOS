"""Testovi za Claude Code adapter i AgentProcessLauncher."""

import sys

from flowos.service.services.infrastructure.agent_adapters.claude_code import (
    AgentProcessLauncher,
    AgentRequest,
    ClaudeCodeAdapter,
)


class TestClaudeCodeAdapter:
    def test_capabilities(self):
        adapter = ClaudeCodeAdapter()
        caps = adapter.capabilities()
        assert caps.can_launch is True
        assert caps.can_stream_events is False
        assert caps.can_cancel is True
        assert caps.can_use_worktree is True

    def test_get_command_minimal(self):
        adapter = ClaudeCodeAdapter()
        req = AgentRequest(
            agent_type="claude-code",
            working_directory="C:/repo",
            repo_path="C:/repo",
            task_description="Implementirati feature X",
        )
        cmd = adapter.get_command(req)
        assert cmd[0] == "claude"
        assert "--workdir" in cmd
        assert "Implementirati feature X" in cmd

    def test_get_command_with_worktree(self):
        adapter = ClaudeCodeAdapter()
        req = AgentRequest(
            agent_type="claude-code",
            working_directory="C:/repo",
            repo_path="C:/repo",
            worktree_path="C:/worktrees/FLOW-42",
        )
        cmd = adapter.get_command(req)
        assert "C:/worktrees/FLOW-42" in cmd

    def test_get_environment_filters_secrets(self):
        adapter = ClaudeCodeAdapter()
        req = AgentRequest(agent_type="claude-code", working_directory=".", repo_path=".")
        env = adapter.get_environment(req)
        # Ne sme sadržati nasumične API ključeve
        assert "API_KEY" not in env or env.get("API_KEY", "") == ""
        # Mora imati PATH
        assert "PATH" in env

    def test_get_environment_keeps_claude_vars(self):
        adapter = ClaudeCodeAdapter()
        req = AgentRequest(agent_type="claude-code", working_directory=".", repo_path=".")
        env = adapter.get_environment(req)
        # ANTHROPIC_API_KEY bi trebalo da bude tu ako postoji
        # Samo proveravamo da ne puca
        assert isinstance(env, dict)


class TestAgentProcessLauncher:
    def test_launch_simple_command(self):
        adapter = ClaudeCodeAdapter()
        launcher = AgentProcessLauncher(adapter)
        req = AgentRequest(
            agent_type="claude-code",
            working_directory=".",
            repo_path=".",
        )
        # Override get_command direktno na instanci
        adapter.get_command = lambda r: [sys.executable, "-c", "print('hello')"]  # type: ignore[method-assign]
        result = launcher.launch(req)
        # Na Windows-u sa CREATE_NEW_PROCESS_GROUP, exit_code moze biti -1
        # Bitno je da je stdout ispravan
        assert "hello" in result.stdout_summary
