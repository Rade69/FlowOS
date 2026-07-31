"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).
"""

import sys

import uvicorn

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.runtime import RuntimeManager


def main() -> int:
    """Glavna ulazna tačka za flowos-service.exe.

    1. Kreira RuntimeManager (lock + port + descriptor)
    2. Kreira FastAPI aplikaciju sa lifespan handlerom
    3. Pokreće uvicorn server
    """
    runtime = RuntimeManager()

    try:
        runtime.acquire_lock()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

    port = runtime.find_free_port()
    runtime.write_descriptor(port)

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
