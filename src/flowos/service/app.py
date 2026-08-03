"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).

Pri startup-u automatski pokreće alembic upgrade head.
"""

import contextlib
import os
import sys

import uvicorn

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.runtime import RuntimeManager


def _run_migrations() -> None:
    """Pokreće alembic upgrade head pre pokretanja servisa."""
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    alembic_ini = os.path.join(exe_dir, "alembic", "alembic.ini")
    if not os.path.isfile(alembic_ini):
        src_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        alembic_ini = os.path.join(src_dir, "alembic", "alembic.ini")

    if not os.path.isfile(alembic_ini):
        return

    with contextlib.suppress(Exception):
        from alembic.config import Config

        from alembic import command

        cfg = Config(alembic_ini)
        command.upgrade(cfg, "head")


def main() -> int:
    """Glavna ulazna tačka za flowos-service.exe."""
    runtime = RuntimeManager()

    try:
        runtime.acquire_lock()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

    port = runtime.find_free_port()
    runtime.write_descriptor(port)

    _run_migrations()
    app = create_app(runtime)

    print(f"FlowOS Service — pokrenut na http://127.0.0.1:{port}")
    print(f"  PID: {runtime.pid}")
    print(f"  Data: {runtime.DESCRIPTOR_DIR.parent / 'data'}")

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except KeyboardInterrupt:
        print("\nFlowOS Service — gašenje...")
    finally:
        runtime.delete_descriptor()
        runtime.release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
