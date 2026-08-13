"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).

Pri startup-u detektuje nesiguran lokalni DB schema drift prije runtime upotrebe.
Legacy bootstrap `create_all()` ostaje, ali eksplicitni repair se pokreće samo
korisničkom/developerskom komandom.
"""

import sys

import uvicorn

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.persistence.engine import get_data_directory
from flowos.service.services.infrastructure.persistence.schema_repair import (
    SchemaRepairRequiredError,
    SchemaState,
    SchemaUnknownDriftError,
    default_database_path,
    inspect_local_schema,
)
from flowos.service.services.infrastructure.runtime import RuntimeManager


def _run_migrations(db_path=None) -> None:
    """Pokreće legacy bootstrap samo ako schema detector ne traži repair."""
    import contextlib

    import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401

    # Importuj sve modele da bi create_all video sve tabele
    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401
    from flowos.service.services.infrastructure.persistence.base import Base
    from flowos.service.services.infrastructure.persistence.engine import (
        create_sqlite_engine,
    )

    target_db_path = db_path or default_database_path()
    inspection = inspect_local_schema(target_db_path)
    if inspection.state == SchemaState.KNOWN_REPAIRABLE_DRIFT:
        raise SchemaRepairRequiredError(inspection)
    if inspection.state == SchemaState.UNKNOWN_DRIFT:
        raise SchemaUnknownDriftError(inspection)

    engine = create_sqlite_engine(target_db_path)
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

    try:
        _run_migrations()
    except SchemaRepairRequiredError as exc:
        print("FlowOS Service — lokalna baza zahtijeva eksplicitni schema repair.", file=sys.stderr)
        print(exc.inspection.message(), file=sys.stderr)
        print(
            "Pokreni: python -m "
            "flowos.service.services.infrastructure.persistence.schema_repair repair-db",
            file=sys.stderr,
        )
        runtime.delete_descriptor()
        runtime.release_lock()
        return 2
    except SchemaUnknownDriftError as exc:
        print("FlowOS Service — lokalna baza ima nepoznat schema drift.", file=sys.stderr)
        print(exc.inspection.message(), file=sys.stderr)
        runtime.delete_descriptor()
        runtime.release_lock()
        return 3

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
