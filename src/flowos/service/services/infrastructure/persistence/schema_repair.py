"""Explicit safe local SQLite schema inspection and repair.

Ovaj modul je uski FLOW-1101A compatibility bridge: detektuje poznati
hibridni lokalni DB drift, pravi backup, popravlja samo dokazivo additivne
objekte, verifikuje ciljnu šemu i tek onda stampuje Alembic head.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.dir_security import harden_existing_directory

ALEMBIC_HEAD = "b7c2e1d4a903"
KNOWN_STALE_REVISIONS = {"03de14cbf6aa", None}

AGENT_REPORT_COLUMNS: dict[str, str] = {
    "id": "VARCHAR(36)",
    "session_id": "VARCHAR(36)",
    "agent_job_id": "VARCHAR(36)",
    "report_type": "VARCHAR(50)",
    "work_status": "VARCHAR(20)",
    "source_report_id": "VARCHAR(36)",
    "source_path": "VARCHAR(2000)",
    "source_content_sha256": "VARCHAR(64)",
    "status": "VARCHAR(20)",
    "scope": "TEXT",
    "impact_summary": "TEXT",
    "reproduction_summary": "TEXT",
    "context_used": "TEXT",
    "summary": "TEXT",
    "rationale": "TEXT",
    "implementation_summary": "TEXT",
    "untouched_scope": "TEXT",
    "verification_summary": "TEXT",
    "independent_review_summary": "TEXT",
    "found_issues": "TEXT",
    "rejected_options": "TEXT",
    "conflicting_sources": "TEXT",
    "commit_shas_json": "TEXT",
    "changed_files_json": "TEXT",
    "open_risks": "TEXT",
    "follow_up": "TEXT",
    "user_confirmation_required": "BOOLEAN",
    "user_verdict": "VARCHAR(20)",
    "user_notes": "TEXT",
    "verdict_audit_json": "TEXT",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}
AGENT_REPORT_NOT_NULL = {"id", "session_id", "status", "user_confirmation_required", "created_at"}
AGENT_REPORT_SOURCE_INDEXES: dict[str, tuple[tuple[str, ...], bool]] = {
    "ix_agent_reports_source_report_id": (("source_report_id",), True),
    "ix_agent_reports_source_path": (("source_path",), True),
}

WORKFLOW_LEDGER_COLUMNS: dict[str, str] = {
    "id": "VARCHAR(36)",
    "project_id": "VARCHAR(36)",
    "event_type": "VARCHAR(80)",
    "session_id": "VARCHAR(36)",
    "task_id": "VARCHAR(36)",
    "plan_item_id": "VARCHAR(36)",
    "source_kind": "VARCHAR(80)",
    "source_id": "VARCHAR(120)",
    "occurred_at": "DATETIME",
    "recorded_at": "DATETIME",
    "idempotency_key": "VARCHAR(300)",
    "payload_json": "TEXT",
}
WORKFLOW_LEDGER_NOT_NULL = {
    "id",
    "project_id",
    "event_type",
    "source_kind",
    "source_id",
    "occurred_at",
    "recorded_at",
    "idempotency_key",
    "payload_json",
}
WORKFLOW_LEDGER_INDEXES: dict[str, tuple[tuple[str, ...], bool]] = {
    "ix_workflow_ledger_project_recorded": (("project_id", "recorded_at"), False),
    "ix_workflow_ledger_project_event_recorded": (
        ("project_id", "event_type", "recorded_at"),
        False,
    ),
    "ix_workflow_ledger_session_recorded": (("session_id", "recorded_at"), False),
    "ix_workflow_ledger_task_recorded": (("task_id", "recorded_at"), False),
    "ix_workflow_ledger_plan_item_recorded": (("plan_item_id", "recorded_at"), False),
    "ix_workflow_ledger_source": (("source_kind", "source_id"), False),
}

REQUIRED_HYBRID_TABLES = {
    "projects",
    "plans",
    "plan_phases",
    "plan_items",
    "tasks",
    "agent_sessions",
    "session_events",
    "agent_reports",
    "session_task_bindings",
    "agent_report_binding_links",
}
PRESERVED_TABLES = (
    "projects",
    "agent_sessions",
    "plan_items",
    "tasks",
    "agent_reports",
    "session_task_bindings",
    "agent_report_binding_links",
)


class SchemaState(StrEnum):
    """Deterministička klasifikacija lokalne SQLite šeme."""

    HEALTHY = "HEALTHY"
    KNOWN_REPAIRABLE_DRIFT = "KNOWN_REPAIRABLE_DRIFT"
    UNKNOWN_DRIFT = "UNKNOWN_DRIFT"


class SchemaRepairRequiredError(RuntimeError):
    """Startup je našao poznati drift koji zahtijeva eksplicitni repair."""

    def __init__(self, inspection: SchemaInspection) -> None:
        self.inspection = inspection
        super().__init__(inspection.message())


class SchemaUnknownDriftError(RuntimeError):
    """Startup/repair je našao drift koji nije dokazivo siguran za popravku."""

    def __init__(self, inspection: SchemaInspection) -> None:
        self.inspection = inspection
        super().__init__(inspection.message())


class SchemaBackupError(RuntimeError):
    """Backup nije uspio; DDL ne smije početi."""


@dataclass(frozen=True)
class SchemaInspection:
    """Rezultat read-only schema introspekcije."""

    db_path: Path
    state: SchemaState
    alembic_version: str | None
    details: list[str] = field(default_factory=list)
    missing_agent_report_columns: list[str] = field(default_factory=list)
    missing_agent_report_indexes: list[str] = field(default_factory=list)
    workflow_ledger_missing: bool = False
    unknown_reasons: list[str] = field(default_factory=list)

    def message(self) -> str:
        parts = [
            f"FlowOS DB schema state: {self.state.value}",
            f"DB: {self.db_path}",
            f"Alembic version: {self.alembic_version or '<missing>'}",
        ]
        if self.details:
            parts.extend(f"- {detail}" for detail in self.details)
        if self.unknown_reasons:
            parts.extend(f"- UNKNOWN: {reason}" for reason in self.unknown_reasons)
        return "\n".join(parts)


@dataclass(frozen=True)
class SchemaBackup:
    """Backup artefakt kreiran prije schema repair DDL-a."""

    path: Path
    database_backup: Path
    copied_wal: Path | None
    copied_shm: Path | None


@dataclass(frozen=True)
class SchemaRepairResult:
    """Ishod eksplicitnog repair pokušaja."""

    initial_state: SchemaState
    final_state: SchemaState
    alembic_version: str | None
    backup_path: Path | None
    changed: bool
    details: list[str]


def default_database_path() -> Path:
    """Vraća produkcijsku lokalnu FlowOS SQLite putanju."""
    from flowos.service.services.infrastructure.persistence.engine import get_data_directory

    return get_data_directory() / "flowos.db"


def inspect_local_schema(db_path: str | Path | None = None) -> SchemaInspection:
    """Read-only klasifikuje lokalnu SQLite šemu."""
    path = Path(db_path) if db_path is not None else default_database_path()
    if not path.exists() or path.stat().st_size == 0:
        return SchemaInspection(
            db_path=path,
            state=SchemaState.HEALTHY,
            alembic_version=None,
            details=["Baza ne postoji ili je prazna; postojeći bootstrap tok smije nastaviti."],
        )

    with _connect_readonly(path) as conn:
        tables = _table_names(conn)
        if not tables:
            return SchemaInspection(
                db_path=path,
                state=SchemaState.HEALTHY,
                alembic_version=None,
                details=["Baza nema tabele; postojeći bootstrap tok smije nastaviti."],
            )

        version = _alembic_version(conn)
        unknown = _unknown_schema_reasons(conn, tables)
        target_errors = _target_schema_errors(conn, tables)

        if not target_errors and version == ALEMBIC_HEAD:
            return SchemaInspection(
                db_path=path,
                state=SchemaState.HEALTHY,
                alembic_version=version,
                details=["Fizička šema i Alembic stamp odgovaraju trenutnom head-u."],
            )

        if unknown:
            return SchemaInspection(
                db_path=path,
                state=SchemaState.UNKNOWN_DRIFT,
                alembic_version=version,
                unknown_reasons=unknown,
            )

        missing_agent_columns = _missing_columns(conn, "agent_reports", AGENT_REPORT_COLUMNS)
        missing_agent_indexes = _missing_indexes(conn, "agent_reports", AGENT_REPORT_SOURCE_INDEXES)
        workflow_missing = "workflow_ledger_events" not in tables
        missing_check = not _agent_report_work_status_check_exists(conn)

        if version in KNOWN_STALE_REVISIONS:
            details = [
                "Poznat hibridni drift: stvarna šema i Alembic stamp nisu usklađeni.",
            ]
            if missing_agent_columns:
                details.append("Nedostaju AgentReport kolone: " + ", ".join(missing_agent_columns))
            if missing_agent_indexes:
                details.append("Nedostaju AgentReport indeksi: " + ", ".join(missing_agent_indexes))
            if missing_check:
                details.append("Nedostaje AgentReport work_status CHECK constraint.")
            if workflow_missing:
                details.append("Nedostaje workflow_ledger_events tabela.")
            if not target_errors:
                details.append("Fizička šema izgleda kompatibilna; potreban je kontrolisan stamp.")
            return SchemaInspection(
                db_path=path,
                state=SchemaState.KNOWN_REPAIRABLE_DRIFT,
                alembic_version=version,
                details=details,
                missing_agent_report_columns=missing_agent_columns,
                missing_agent_report_indexes=missing_agent_indexes,
                workflow_ledger_missing=workflow_missing,
            )

        return SchemaInspection(
            db_path=path,
            state=SchemaState.UNKNOWN_DRIFT,
            alembic_version=version,
            unknown_reasons=target_errors
            or [f"Alembic version nije poznata za FLOW-1101A repair: {version!r}."],
        )


def repair_database(db_path: str | Path | None = None) -> SchemaRepairResult:
    """Eksplicitno popravlja poznati lokalni hibridni drift.

    Funkcija nikada ne radi blind upgrade/stamp: ako šema nije HEALTHY ili
    poznati repairable drift, odbija rad. Backup se kreira prije bilo kog DDL-a.
    """
    path = Path(db_path) if db_path is not None else default_database_path()
    inspection = inspect_local_schema(path)
    if inspection.state == SchemaState.HEALTHY:
        return SchemaRepairResult(
            initial_state=inspection.state,
            final_state=inspection.state,
            alembic_version=inspection.alembic_version,
            backup_path=None,
            changed=False,
            details=["Baza je već zdrava; repair je no-op."],
        )
    if inspection.state == SchemaState.UNKNOWN_DRIFT:
        raise SchemaUnknownDriftError(inspection)

    backup = create_schema_backup(path)
    details: list[str] = []

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        before = _preserved_snapshot_from_connection(conn)
        tables = _table_names(conn)
        if _agent_reports_needs_rebuild(conn):
            _rebuild_agent_reports(conn)
            details.append("agent_reports tabela rebuildana sa v2/source identity šemom.")
        else:
            _ensure_agent_report_indexes(conn)
            details.append("agent_reports tabela je već imala potrebne kolone/check.")

        tables = _table_names(conn)
        if "workflow_ledger_events" not in tables:
            _create_workflow_ledger_events(conn)
            details.append("workflow_ledger_events tabela kreirana.")
        else:
            _ensure_workflow_ledger_indexes(conn)
            details.append("workflow_ledger_events tabela je već postojala.")

        _verify_pre_stamp_repair(conn, path, before)
        _stamp_head(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()

    after = _preserved_snapshot(path)
    if before != after:
        raise SchemaUnknownDriftError(
            SchemaInspection(
                db_path=path,
                state=SchemaState.UNKNOWN_DRIFT,
                alembic_version=None,
                unknown_reasons=["Repair je promijenio reprezentativne postojeće podatke."],
            )
        )

    final = inspect_local_schema(path)
    if final.state != SchemaState.HEALTHY:
        raise SchemaUnknownDriftError(final)
    _verify_orm_access(path)
    details.append("Alembic stamp postavljen nakon schema/ORM verifikacije.")
    return SchemaRepairResult(
        initial_state=inspection.state,
        final_state=final.state,
        alembic_version=final.alembic_version,
        backup_path=backup.path,
        changed=True,
        details=details,
    )


def create_schema_backup(db_path: str | Path) -> SchemaBackup:
    """Kreira collision-safe SQLite-aware backup prije repair DDL-a."""
    source = Path(db_path)
    if not source.exists():
        raise SchemaBackupError(f"Baza ne postoji: {source}")

    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = source.parent / "backups" / f"schema-repair-{stamp}-{uuid.uuid4()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    # FLOW-1108: hardenuje TEK kreiran, collision-safe backup direktorijum —
    # ne dira mkdir(exist_ok=False) semantiku iznad, samo ograničava ACL na
    # direktorijumu koji sadrži kopiju cijele baze.
    harden_existing_directory(backup_dir)
    backup_db = backup_dir / source.name

    try:
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(str(backup_db))
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
            src.close()

        copied_wal = _copy_if_present(source.with_name(source.name + "-wal"), backup_dir)
        copied_shm = _copy_if_present(source.with_name(source.name + "-shm"), backup_dir)
        metadata = {
            "source": str(source),
            "database_backup": str(backup_db),
            "copied_wal": str(copied_wal) if copied_wal else None,
            "copied_shm": str(copied_shm) if copied_shm else None,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "method": "sqlite_backup_api_plus_wal_shm_artifacts_when_present",
        }
        (backup_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        with sqlite3.connect(":memory:"):
            pass
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise SchemaBackupError(f"Backup nije uspio: {exc}") from exc

    return SchemaBackup(
        path=backup_dir, database_backup=backup_db, copied_wal=copied_wal, copied_shm=copied_shm
    )


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def _alembic_version(conn: sqlite3.Connection) -> str | None:
    if "alembic_version" not in _table_names(conn):
        return None
    rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1:
        return None
    return str(rows[0]["version_num"])


def _columns(conn: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {str(row["name"]): row for row in conn.execute(f"PRAGMA table_info({table})")}


def _missing_columns(conn: sqlite3.Connection, table: str, expected: dict[str, str]) -> list[str]:
    existing = _columns(conn, table)
    return sorted(set(expected) - set(existing))


def _normalize_type(value: str | None) -> str:
    return (value or "").upper().replace(" ", "")


def _type_compatible(actual: str | None, expected: str) -> bool:
    return _normalize_type(actual) == _normalize_type(expected)


def _index_details(conn: sqlite3.Connection, table: str) -> dict[str, tuple[tuple[str, ...], bool]]:
    details: dict[str, tuple[tuple[str, ...], bool]] = {}
    for row in conn.execute(f"PRAGMA index_list({table})").fetchall():
        name = str(row["name"])
        columns = tuple(
            str(info["name"]) for info in conn.execute(f"PRAGMA index_info('{name}')").fetchall()
        )
        details[name] = (columns, bool(row["unique"]))
    return details


def _missing_indexes(
    conn: sqlite3.Connection, table: str, expected: dict[str, tuple[tuple[str, ...], bool]]
) -> list[str]:
    existing = _index_details(conn, table)
    return sorted(name for name in expected if name not in existing)


def _unknown_schema_reasons(conn: sqlite3.Connection, tables: set[str]) -> list[str]:
    reasons: list[str] = []
    missing_tables = sorted(REQUIRED_HYBRID_TABLES - tables)
    if missing_tables:
        reasons.append("Nedostaju required hybrid tabele: " + ", ".join(missing_tables))
        return reasons

    reasons.extend(
        _column_conflicts(conn, "agent_reports", AGENT_REPORT_COLUMNS, AGENT_REPORT_NOT_NULL)
    )
    reasons.extend(_index_conflicts(conn, "agent_reports", AGENT_REPORT_SOURCE_INDEXES))

    if "workflow_ledger_events" in tables:
        reasons.extend(
            _column_conflicts(
                conn,
                "workflow_ledger_events",
                WORKFLOW_LEDGER_COLUMNS,
                WORKFLOW_LEDGER_NOT_NULL,
            )
        )
        reasons.extend(_index_conflicts(conn, "workflow_ledger_events", WORKFLOW_LEDGER_INDEXES))
        if not _workflow_idempotency_unique_exists(conn):
            reasons.append("workflow_ledger_events nema unique idempotency constraint/index.")

    if "work_status" in _columns(conn, "agent_reports"):
        invalid = conn.execute(
            "SELECT COUNT(*) AS count FROM agent_reports "
            "WHERE work_status IS NOT NULL "
            "AND work_status NOT IN ('completed', 'partial', 'blocked')"
        ).fetchone()["count"]
        if invalid:
            reasons.append("agent_reports.work_status sadrži vrijednosti izvan target enum-a.")

    return reasons


def _column_conflicts(
    conn: sqlite3.Connection,
    table: str,
    expected: dict[str, str],
    not_null: set[str],
) -> list[str]:
    if table not in _table_names(conn):
        return []
    conflicts: list[str] = []
    existing = _columns(conn, table)
    for name, expected_type in expected.items():
        if name not in existing:
            continue
        row = existing[name]
        if not _type_compatible(str(row["type"]), expected_type):
            conflicts.append(
                f"{table}.{name} ima tip {row['type']!r}, očekivano {expected_type!r}."
            )
        if name in not_null and not bool(row["notnull"]) and not bool(row["pk"]):
            conflicts.append(f"{table}.{name} nije NOT NULL kao u target šemi.")
    return conflicts


def _index_conflicts(
    conn: sqlite3.Connection,
    table: str,
    expected: dict[str, tuple[tuple[str, ...], bool]],
) -> list[str]:
    if table not in _table_names(conn):
        return []
    existing = _index_details(conn, table)
    conflicts: list[str] = []
    for name, shape in expected.items():
        if name in existing and existing[name] != shape:
            conflicts.append(f"{table}.{name} ima shape {existing[name]!r}, očekivano {shape!r}.")
    return conflicts


def _target_schema_errors(conn: sqlite3.Connection, tables: set[str]) -> list[str]:
    errors: list[str] = []
    if "agent_reports" not in tables:
        errors.append("agent_reports tabela ne postoji.")
    else:
        for column in _missing_columns(conn, "agent_reports", AGENT_REPORT_COLUMNS):
            errors.append(f"agent_reports.{column} ne postoji.")
        for index in _missing_indexes(conn, "agent_reports", AGENT_REPORT_SOURCE_INDEXES):
            errors.append(f"agent_reports index {index} ne postoji.")
        if not _agent_report_work_status_check_exists(conn):
            errors.append("agent_reports work_status CHECK constraint ne postoji.")

    if "workflow_ledger_events" not in tables:
        errors.append("workflow_ledger_events tabela ne postoji.")
    else:
        for column in _missing_columns(conn, "workflow_ledger_events", WORKFLOW_LEDGER_COLUMNS):
            errors.append(f"workflow_ledger_events.{column} ne postoji.")
        for index in _missing_indexes(conn, "workflow_ledger_events", WORKFLOW_LEDGER_INDEXES):
            errors.append(f"workflow_ledger_events index {index} ne postoji.")
        if not _workflow_idempotency_unique_exists(conn):
            errors.append("workflow_ledger_events unique idempotency constraint ne postoji.")

    return errors


def _agent_report_work_status_check_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_reports'"
    ).fetchone()
    sql = str(row["sql"] if row else "")
    return (
        "ck_agent_reports_work_status" in sql
        or "work_status IS NULL OR work_status IN ('completed', 'partial', 'blocked')" in sql
    )


def _workflow_idempotency_unique_exists(conn: sqlite3.Connection) -> bool:
    indexes = _index_details(conn, "workflow_ledger_events")
    return any(columns == ("idempotency_key",) and unique for columns, unique in indexes.values())


def _agent_reports_needs_rebuild(conn: sqlite3.Connection) -> bool:
    return bool(_missing_columns(conn, "agent_reports", AGENT_REPORT_COLUMNS)) or (
        not _agent_report_work_status_check_exists(conn)
    )


def _rebuild_agent_reports(conn: sqlite3.Connection) -> None:
    temp_table = "agent_reports__flowos_repair"
    conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
    conn.execute(_agent_reports_create_sql(temp_table))

    old_columns = _columns(conn, "agent_reports")
    target_columns = list(AGENT_REPORT_COLUMNS)
    select_parts = [name if name in old_columns else "NULL" for name in target_columns]
    conn.execute(
        f"INSERT INTO {temp_table} ({', '.join(target_columns)}) "
        f"SELECT {', '.join(select_parts)} FROM agent_reports"
    )
    conn.execute("DROP TABLE agent_reports")
    conn.execute(f"ALTER TABLE {temp_table} RENAME TO agent_reports")
    conn.execute("CREATE INDEX ix_agent_reports_session_id ON agent_reports (session_id)")
    conn.execute("CREATE INDEX ix_agent_reports_status ON agent_reports (status)")
    _ensure_agent_report_indexes(conn)


def _agent_reports_create_sql(table_name: str) -> str:
    return f"""
CREATE TABLE {table_name} (
    id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    agent_job_id VARCHAR(36),
    report_type VARCHAR(50),
    work_status VARCHAR(20),
    source_report_id VARCHAR(36),
    source_path VARCHAR(2000),
    source_content_sha256 VARCHAR(64),
    status VARCHAR(20) NOT NULL,
    scope TEXT,
    impact_summary TEXT,
    reproduction_summary TEXT,
    context_used TEXT,
    summary TEXT,
    rationale TEXT,
    implementation_summary TEXT,
    untouched_scope TEXT,
    verification_summary TEXT,
    independent_review_summary TEXT,
    found_issues TEXT,
    rejected_options TEXT,
    conflicting_sources TEXT,
    commit_shas_json TEXT,
    changed_files_json TEXT,
    open_risks TEXT,
    follow_up TEXT,
    user_confirmation_required BOOLEAN NOT NULL,
    user_verdict VARCHAR(20),
    user_notes TEXT,
    verdict_audit_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT ck_agent_reports_work_status
        CHECK (work_status IS NULL OR work_status IN ('completed', 'partial', 'blocked')),
    FOREIGN KEY(session_id) REFERENCES agent_sessions (id) ON DELETE CASCADE
)
"""


def _ensure_agent_report_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_reports_source_report_id "
        "ON agent_reports (source_report_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_reports_source_path "
        "ON agent_reports (source_path)"
    )


def _create_workflow_ledger_events(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
CREATE TABLE workflow_ledger_events (
    id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    session_id VARCHAR(36),
    task_id VARCHAR(36),
    plan_item_id VARCHAR(36),
    source_kind VARCHAR(80) NOT NULL,
    source_id VARCHAR(120) NOT NULL,
    occurred_at DATETIME NOT NULL,
    recorded_at DATETIME NOT NULL,
    idempotency_key VARCHAR(300) NOT NULL,
    payload_json TEXT DEFAULT '{}' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_workflow_ledger_events_idempotency_key UNIQUE (idempotency_key),
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    FOREIGN KEY(session_id) REFERENCES agent_sessions (id) ON DELETE SET NULL,
    FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL,
    FOREIGN KEY(plan_item_id) REFERENCES plan_items (id) ON DELETE SET NULL
)
"""
    )
    _ensure_workflow_ledger_indexes(conn)


def _ensure_workflow_ledger_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_project_recorded "
        "ON workflow_ledger_events (project_id, recorded_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_project_event_recorded "
        "ON workflow_ledger_events (project_id, event_type, recorded_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_session_recorded "
        "ON workflow_ledger_events (session_id, recorded_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_task_recorded "
        "ON workflow_ledger_events (task_id, recorded_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_plan_item_recorded "
        "ON workflow_ledger_events (plan_item_id, recorded_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_ledger_source "
        "ON workflow_ledger_events (source_kind, source_id)"
    )


def _stamp_head(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("DELETE FROM alembic_version")
    conn.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (ALEMBIC_HEAD,))


def _verify_pre_stamp_repair(
    conn: sqlite3.Connection, db_path: Path, before: dict[str, list[tuple]]
) -> None:
    """Verifikuje target šemu i podatke prije Alembic stamp-a i commit-a."""
    target_errors = _target_schema_errors(conn, _table_names(conn))
    if target_errors:
        raise SchemaUnknownDriftError(
            SchemaInspection(
                db_path=db_path,
                state=SchemaState.UNKNOWN_DRIFT,
                alembic_version=_alembic_version(conn),
                unknown_reasons=target_errors,
            )
        )
    after = _preserved_snapshot_from_connection(conn)
    if before != after:
        raise SchemaUnknownDriftError(
            SchemaInspection(
                db_path=db_path,
                state=SchemaState.UNKNOWN_DRIFT,
                alembic_version=_alembic_version(conn),
                unknown_reasons=["Repair je promijenio reprezentativne postojeće podatke."],
            )
        )
    _verify_required_column_selects(conn)


def _verify_required_column_selects(conn: sqlite3.Connection) -> None:
    """Vježba sve kolone koje current ORM očekuje prije stamp/commit granice."""
    conn.execute(
        "SELECT " + ", ".join(AGENT_REPORT_COLUMNS) + " FROM agent_reports ORDER BY id LIMIT 1"
    ).fetchall()
    conn.execute(
        "SELECT "
        + ", ".join(WORKFLOW_LEDGER_COLUMNS)
        + " FROM workflow_ledger_events ORDER BY id LIMIT 1"
    ).fetchall()


def _preserved_snapshot(db_path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return _preserved_snapshot_from_connection(conn)


def _preserved_snapshot_from_connection(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    tables = _table_names(conn)
    snapshot: dict[str, list[tuple]] = {}
    for table in PRESERVED_TABLES:
        if table not in tables:
            snapshot[table] = []
            continue
        columns = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")]
        selected: list[str] = [
            col
            for col in ("id", "name", "title", "repo_path", "status", "session_id")
            if col in columns
        ]
        if not selected:
            selected = ["id"] if "id" in columns else columns[:1]
        rows = conn.execute(
            f"SELECT {', '.join(selected)} FROM {table} ORDER BY {selected[0]}"
        ).fetchall()
        snapshot[table] = [tuple(row) for row in rows]
    return snapshot


def _verify_orm_access(db_path: Path) -> None:
    import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401
    from flowos.service.services.infrastructure.persistence.report_models import AgentReport
    from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
        WorkflowLedgerEvent,
    )

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with Session(engine) as session:
            session.query(AgentReport).first()
            session.query(WorkflowLedgerEvent).count()
    finally:
        engine.dispose()


def _copy_if_present(path: Path, backup_dir: Path) -> Path | None:
    if not path.exists():
        return None
    target = backup_dir / path.name
    shutil.copy2(path, target)
    return target


def _print_result(result: SchemaRepairResult) -> None:
    payload = {
        "initial_state": result.initial_state.value,
        "final_state": result.final_state.value,
        "alembic_version": result.alembic_version,
        "backup_path": str(result.backup_path) if result.backup_path else None,
        "changed": result.changed,
        "details": result.details,
    }
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point za eksplicitni schema repair."""
    parser = argparse.ArgumentParser(description="FlowOS local DB schema inspection/repair")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "repair-db"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--db-path", default=None)

    args = parser.parse_args(argv)
    db_path = Path(args.db_path) if args.db_path else default_database_path()
    try:
        if args.command == "inspect":
            inspection = inspect_local_schema(db_path)
            sys.stdout.write(inspection.message() + "\n")
            return 0 if inspection.state == SchemaState.HEALTHY else 2
        result = repair_database(db_path)
        _print_result(result)
        return 0
    except SchemaUnknownDriftError as exc:
        sys.stderr.write(exc.inspection.message() + "\n")
        return 3
    except SchemaBackupError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
