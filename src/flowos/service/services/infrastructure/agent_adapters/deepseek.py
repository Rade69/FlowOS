"""DeepSeek adapter — OpenAI-kompatibilni API.

DeepSeek API: https://api.deepseek.com/v1
Modeli: deepseek-chat (V3), deepseek-reasoner (R1)

Koristi httpx za HTTP pozive (ne uvodi openai paket).
Isti AgentAdapter protokol kao Claude Code.
"""

import json
import os
import sys
from dataclasses import dataclass

from flowos.service.services.infrastructure.agent_adapters.claude_code import (
    AdapterCapabilities,
    AgentRequest,
)


@dataclass
class DeepSeekConfig:
    """Konfiguracija za DeepSeek API."""

    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    default_model: str = "deepseek-chat"


class DeepSeekAdapter:
    """Adapter za DeepSeek API (OpenAI-kompatibilan).

    Koristi httpx za direktne HTTP pozive.
    Podržava OpenAI SDK kompatibilnost za buduću upotrebu.
    """

    AGENT_TYPE = "deepseek"

    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        self._config = config or DeepSeekConfig(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            can_launch=True,
            can_stream_events=False,
            can_report_usage=True,
            can_cancel=True,
            can_use_worktree=True,
        )

    def get_command(self, request: AgentRequest) -> list[str]:
        """DeepSeek koristi Python + httpx, ne eksterni CLI.

        Za CLI režim, može se koristiti `openai` CLI alat ako je instaliran.
        """
        model = request.model_name or self._config.default_model

        # DeepSeek API poziv kroz Python
        return [
            sys.executable,
            "-c",
            self._build_inline_script(request.task_description or "", model),
        ]

    def get_environment(self, request: AgentRequest) -> dict[str, str]:
        """Prosleđuje DEEPSEEK_API_KEY u environment."""
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
        env = {k: v for k, v in os.environ.items() if k in safe_keys or k.startswith("DEEPSEEK_")}
        env["DEEPSEEK_API_KEY"] = self._config.api_key
        env["DEEPSEEK_BASE_URL"] = self._config.base_url
        return env

    def _build_inline_script(self, task: str, model: str) -> str:
        """Pravi inline Python skriptu za DeepSeek API poziv."""
        return f'''
import json, os, sys
api_key = os.environ.get("DEEPSEEK_API_KEY", "{self._config.api_key}")
base_url = os.environ.get("DEEPSEEK_BASE_URL", "{self._config.base_url}")
task = {json.dumps(task)}

try:
    import urllib.request
    data = json.dumps({{"model": "{model}", "messages": [{{"role": "user", "content": task}}], "max_tokens": 4096}}).encode()
    req = urllib.request.Request(
        f"{{base_url}}/chat/completions",
        data=data,
        headers={{"Authorization": f"Bearer {{api_key}}", "Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]
        print(content)
        # Zapiši usage
        usage = result.get("usage", {{}})
        print(f"\\n[DEEPSEEK_USAGE] input={{usage.get('prompt_tokens',0)}} output={{usage.get('completion_tokens',0)}}", file=sys.stderr)
except Exception as e:
    print(f"DeepSeek API error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''


# ═══════════════════════════════════════════════════════════════════
# Factory funkcija za kreiranje adaptera
# ═══════════════════════════════════════════════════════════════════


def create_deepseek_adapter(api_key: str | None = None) -> DeepSeekAdapter:
    """Kreira DeepSeek adapter sa API ključem.

    Args:
        api_key: DeepSeek API ključ. Ako nije prosleđen, čita DEEPSEEK_API_KEY iz env.

    Returns:
        Konfigurisan DeepSeekAdapter.
    """
    config = DeepSeekConfig(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
    )
    return DeepSeekAdapter(config)


# Registracija adaptera po imenu
ADAPTER_REGISTRY: dict[str, str] = {
    "claude-code": "ClaudeCodeAdapter",
    "deepseek": "DeepSeekAdapter",
    "pi": "PiAdapter",  # TODO: FLOW-307
}


def get_available_agents() -> list[str]:
    """Vraća listu dostupnih agentskih adaptera."""
    return list(ADAPTER_REGISTRY.keys())
