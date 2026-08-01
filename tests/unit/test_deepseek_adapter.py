"""Testovi za DeepSeek adapter."""

from flowos.service.services.infrastructure.agent_adapters.deepseek import (
    DeepSeekAdapter,
    DeepSeekConfig,
    create_deepseek_adapter,
    get_available_agents,
)


class TestDeepSeekAdapter:
    def test_capabilities(self):
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="test"))
        caps = adapter.capabilities()
        assert caps.can_launch is True
        assert caps.can_report_usage is True

    def test_get_command_uses_default_model(self):
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="test"))
        from flowos.service.services.infrastructure.agent_adapters.claude_code import AgentRequest

        req = AgentRequest(agent_type="deepseek", working_directory=".", repo_path=".", task_description="Test task")
        cmd = adapter.get_command(req)
        assert "deepseek-chat" in cmd[2]

    def test_get_command_uses_custom_model(self):
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="test"))
        from flowos.service.services.infrastructure.agent_adapters.claude_code import AgentRequest

        req = AgentRequest(agent_type="deepseek", working_directory=".", repo_path=".", model_name="deepseek-reasoner", task_description="Test")
        cmd = adapter.get_command(req)
        assert "deepseek-reasoner" in cmd[2]

    def test_get_environment_includes_api_key(self):
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="sk-test-key"))
        from flowos.service.services.infrastructure.agent_adapters.claude_code import AgentRequest

        req = AgentRequest(agent_type="deepseek", working_directory=".", repo_path=".")
        env = adapter.get_environment(req)
        assert env["DEEPSEEK_API_KEY"] == "sk-test-key"
        assert "PATH" in env

    def test_create_adapter_from_env(self):
        import os

        os.environ["DEEPSEEK_API_KEY"] = "sk-from-env"
        adapter = create_deepseek_adapter()
        assert adapter._config.api_key == "sk-from-env"

    def test_available_agents(self):
        agents = get_available_agents()
        assert "deepseek" in agents
        assert "claude-code" in agents