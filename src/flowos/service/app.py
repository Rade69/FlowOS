"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).
"""

import sys


def main() -> int:
    """Glavna ulazna tačka za flowos-service.exe.

    Čita runtime descriptor, bira slobodan port, pokreće uvicorn.
    """
    # Skeleton — ne pokrećemo stvarni server dok ne postoje rute
    print("FlowOS Service — skeleton pokrenut (nema još endpoint-a)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
