"""Agent Process Scanner — detektuje agentske procese."""

import subprocess
from datetime import UTC, datetime

AGENT_NAMES = ["claude", "codex", "crush", "pi", "cline", "cursor"]


def scan_agents() -> list[dict]:
    """Skenira procese i pronalazi agentske procese."""
    agents: list[dict] = []
    now = datetime.now(tz=UTC).isoformat()
    seen_pids: set[int] = set()

    try:
        for name in AGENT_NAMES:
            result = subprocess.run(
                ["tasklist", "/fi", f"IMAGENAME eq {name}*", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("INFO:"):
                    continue
                parts = line.replace('"', "").split(",")
                if len(parts) >= 2:
                    image = parts[0].strip()
                    try:
                        pid = int(parts[1].strip())
                    except ValueError:
                        continue
                    if pid in seen_pids:
                        continue
                    seen_pids.add(pid)
                    agents.append(
                        {
                            "pid": pid,
                            "agent_type": name.title(),
                            "image": image,
                            "detected_at": now,
                        }
                    )
    except Exception:
        pass

    return agents
