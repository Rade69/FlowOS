"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).

Pri startup-u automatski dodaje kolone koje nedostaju (direktne SQL migracije).
"""

import sys

import uvicorn

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.persistence.engine import get_data_directory
from flowos.service.services.infrastructure.runtime import RuntimeManager


def _run_migrations() -> None:
    """Dodaje kolone koje nedostaju koristeći SQLAlchemy engine."""
    import contextlib

    from flowos.service.services.infrastructure.persistence.base import Base
    from flowos.service.services.infrastructure.persistence.engine import (
        create_sqlite_engine,
    )

    engine = create_sqlite_engine()
    with contextlib.suppress(Exception):
        # Kreiraj sve tabele ako ne postoje (sa svim novim kolonama)
        Base.metadata.create_all(engine)

    # Dodaj kolone koje create_all ne može da doda na postojeće tabele
    with contextlib.suppress(Exception), engine.connect() as conn:
        conn.exec_driver_sql("ALTER TABLE agent_sessions ADD COLUMN last_heartbeat_at TIMESTAMP")
        conn.commit()


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
    print(f"  Data: {get_data_directory()}")

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except KeyboardInterrupt:
        print("\nFlowOS Service — gasenje...")
    finally:
        runtime.delete_descriptor()
        runtime.release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
