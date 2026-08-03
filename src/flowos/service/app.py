"""FlowOS Service — FastAPI backend aplikacija.

Jedini vlasnik baze, watchera, Git operacija i agentskih procesa.
Sluša samo na 127.0.0.1. Komunicira sa GUI-jem preko REST + WebSocket,
sa CLI-jem preko REST (+ offline JSONL spool).

Pri startup-u automatski dodaje kolone koje nedostaju (direktne SQL migracije).
"""

import contextlib
import logging
import sqlite3
import sys

import uvicorn

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.persistence.engine import get_data_directory
from flowos.service.services.infrastructure.runtime import RuntimeManager


def _run_migrations() -> None:
    """Dodaje kolone koje nedostaju na postojećim tabelama."""
    db_path = get_data_directory() / "flowos.db"
    if not db_path.exists():
        return

    logger = logging.getLogger("flowos.migrations")
    migrations = [
        "ALTER TABLE agent_sessions ADD COLUMN last_heartbeat_at TIMESTAMP",
        """CREATE TABLE IF NOT EXISTS worktrees (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, task_id TEXT,
            session_id TEXT, worktree_path TEXT NOT NULL, branch_name TEXT NOT NULL,
            base_branch TEXT, base_commit_sha TEXT, status TEXT NOT NULL DEFAULT "ACTIVE",
            is_clean INTEGER NOT NULL DEFAULT 1, has_conflicts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL, last_activity_at TIMESTAMP,
            integrated_at TIMESTAMP, cleaned_at TIMESTAMP,
            retention_days INTEGER NOT NULL DEFAULT 7,
            result_commit_sha TEXT, integration_verified INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE SET NULL
        )""",
    ]

    with contextlib.suppress(Exception):
        conn = sqlite3.connect(str(db_path))
        for sql in migrations:
            try:
                conn.execute(sql)
                logger.info("Migracija uspesna")
            except sqlite3.OperationalError:
                pass  # Kolona već postoji
        conn.commit()
        conn.close()


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
