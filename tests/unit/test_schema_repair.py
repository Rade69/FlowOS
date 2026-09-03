"""Regresioni testovi za FLOW-1101A eksplicitni lokalni DB schema repair."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401
from flowos.service.app import _run_migrations
from flowos.service.services.infrastructure.persistence.report_models import AgentReport
from flowos.service.services.infrastructure.persistence.schema_repair import (
    ALEMBIC_HEAD,
    SchemaBackupError,
    SchemaRepairRequiredError,
    SchemaState,
    SchemaUnknownDriftError,
    inspect_local_schema,
    repair_database,
)
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)


def _create_known_hybrid_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
INSERT INTO alembic_version (version_num) VALUES ('03de14cbf6aa');

CREATE TABLE projects (
    id VARCHAR(36) NOT NULL,
    name VARCHAR(200) NOT NULL,
    repo_path VARCHAR(1000) NOT NULL,
    status VARCHAR(20) NOT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    PRIMARY KEY (id)
);
CREATE INDEX ix_projects_status ON projects (status);

CREATE TABLE plans (
    id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    title VARCHAR(300) NOT NULL,
    source_artifact_id VARCHAR(36),
    status VARCHAR(20) NOT NULL,
    activated_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    PRIMARY KEY (id)
);

CREATE TABLE plan_phases (
    id VARCHAR(36) NOT NULL,
    plan_id VARCHAR(36) NOT NULL,
    phase_key VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    sequence INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_plan_phases_key UNIQUE (plan_id, phase_key)
);

CREATE TABLE plan_items (
    id VARCHAR(36) NOT NULL,
    plan_phase_id VARCHAR(36) NOT NULL,
    item_key VARCHAR(30) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    sequence INTEGER NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    progress_source VARCHAR(20) NOT NULL,
    owner_session_id VARCHAR(36),
    started_at DATETIME,
    implemented_at DATETIME,
    verified_at DATETIME,
    accepted_at DATETIME,
    blocked_reason TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    PRIMARY KEY (id)
);
CREATE INDEX ix_plan_items_item_key ON plan_items (item_key);
CREATE INDEX ix_plan_items_phase_id ON plan_items (plan_phase_id);
CREATE INDEX ix_plan_items_status ON plan_items (status);

CREATE TABLE tasks (
    id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL,
    priority VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    done_at DATETIME,
    plan_item_id VARCHAR(36),
    PRIMARY KEY (id)
);
CREATE INDEX ix_tasks_project_id ON tasks (project_id);
CREATE INDEX ix_tasks_status ON tasks (status);
CREATE INDEX ix_tasks_priority ON tasks (priority);

CREATE TABLE agent_sessions (
    id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36),
    project_id VARCHAR(36) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    model_name VARCHAR(50),
    execution_mode VARCHAR(30) NOT NULL,
    terminal_label VARCHAR(100),
    working_directory VARCHAR(1000),
    repo_path VARCHAR(1000) NOT NULL,
    branch_name VARCHAR(500),
    worktree_path VARCHAR(1000),
    base_commit_sha VARCHAR(40),
    pid INTEGER,
    status VARCHAR(20) NOT NULL,
    started_at DATETIME,
    last_activity_at DATETIME,
    last_heartbeat_at DATETIME,
    ended_at DATETIME,
    exit_code INTEGER,
    result_commit_sha VARCHAR(40),
    plan_item_id VARCHAR(36),
    PRIMARY KEY (id)
);
CREATE INDEX ix_agent_sessions_project_id ON agent_sessions (project_id);
CREATE INDEX ix_agent_sessions_task_id ON agent_sessions (task_id);
CREATE INDEX ix_agent_sessions_status ON agent_sessions (status);
CREATE INDEX ix_agent_sessions_execution_mode ON agent_sessions (execution_mode);

CREATE TABLE session_events (
    id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    summary VARCHAR(500) NOT NULL,
    payload_json TEXT,
    source VARCHAR(20) NOT NULL,
    idempotency_key VARCHAR(100),
    occurred_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (idempotency_key)
);

CREATE TABLE agent_reports (
    id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    agent_job_id VARCHAR(36),
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
    PRIMARY KEY (id)
);
CREATE INDEX ix_agent_reports_session_id ON agent_reports (session_id);
CREATE INDEX ix_agent_reports_status ON agent_reports (status);

CREATE TABLE session_task_bindings (
    id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36),
    plan_item_id VARCHAR(36),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    binding_source VARCHAR(30) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_session_task_bindings_single_target
        CHECK (NOT (task_id IS NOT NULL AND plan_item_id IS NOT NULL)),
    CONSTRAINT ck_session_task_bindings_time_order CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT ck_session_task_bindings_source CHECK (binding_source IN ('USER', 'LEGACY_DIRECT_FK'))
);
CREATE INDEX ix_session_task_bindings_session_id ON session_task_bindings (session_id);
CREATE INDEX ix_session_task_bindings_task_id ON session_task_bindings (task_id);
CREATE INDEX ix_session_task_bindings_plan_item_id ON session_task_bindings (plan_item_id);
CREATE INDEX ix_session_task_bindings_started_at ON session_task_bindings (started_at);
CREATE UNIQUE INDEX uq_session_task_bindings_active
    ON session_task_bindings (session_id) WHERE ended_at IS NULL;

CREATE TABLE agent_report_binding_links (
    id VARCHAR(36) NOT NULL,
    report_id VARCHAR(36) NOT NULL,
    session_task_binding_id VARCHAR(36) NOT NULL,
    resolved_plan_item_id VARCHAR(36),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_agent_report_binding_links_report_binding
        UNIQUE (report_id, session_task_binding_id)
);
CREATE INDEX ix_agent_report_binding_links_report_id ON agent_report_binding_links (report_id);
CREATE INDEX ix_agent_report_binding_links_binding_id
    ON agent_report_binding_links (session_task_binding_id);
"""
        )
        conn.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "project-1",
                "FlowOS",
                "C:/repo",
                "ACTIVE",
                "preserve-project",
                "2026-08-13T00:00:00",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("plan-1", "project-1", "Plan", None, "ACTIVE", None, "2026-08-13T00:00:00", None),
        )
        conn.execute(
            "INSERT INTO plan_phases VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("phase-1", "plan-1", "F11", "Faza 11", None, 11, "ACTIVE", "2026-08-13T00:00:00"),
        )
        conn.execute(
            "INSERT INTO plan_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "plan-item-1",
                "phase-1",
                "FLOW-1101A",
                "Schema repair",
                "preserve-plan-item",
                1,
                "HIGH",
                "IN_PROGRESS",
                "MANUAL",
                None,
                None,
                None,
                None,
                None,
                None,
                "2026-08-13T00:00:00",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "task-1",
                "project-1",
                "Task",
                "preserve-task",
                "OPEN",
                "NORMAL",
                "2026-08-13T00:00:00",
                None,
                None,
                "plan-item-1",
            ),
        )
        conn.execute(
            "INSERT INTO agent_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "session-1",
                "task-1",
                "project-1",
                "codex",
                "gpt-5",
                "WRAPPED_TERMINAL",
                None,
                None,
                "C:/repo",
                "main",
                None,
                "abc",
                None,
                "ACTIVE",
                "2026-08-13T00:00:00",
                None,
                None,
                None,
                None,
                None,
                "plan-item-1",
            ),
        )
        conn.execute(
            "INSERT INTO agent_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "report-1",
                "session-1",
                None,
                "DRAFT",
                "scope",
                None,
                None,
                None,
                "preserve-report",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                None,
                None,
                None,
                "2026-08-13T00:00:00",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO session_task_bindings VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "binding-1",
                "session-1",
                "task-1",
                None,
                "2026-08-13T00:00:00",
                None,
                "USER",
            ),
        )
        conn.execute(
            "INSERT INTO agent_report_binding_links VALUES (?, ?, ?, ?, ?)",
            ("link-1", "report-1", "binding-1", "plan-item-1", "2026-08-13T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_one(db_path: Path, sql: str):
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


def _columns(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def _indexes(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return [row[1] for row in conn.execute(f"PRAGMA index_list({table})")]
    finally:
        conn.close()


def _set_alembic_version(db_path: Path, version: str) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (version,))
        conn.commit()
    finally:
        conn.close()


def _create_alembic_db(db_path: Path, revision: str = "head") -> None:
    url = f"sqlite:///{db_path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", revision],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def _create_fresh_alembic_head_db(db_path: Path) -> None:
    _create_alembic_db(db_path)


def _foreign_key_check(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()


def _snapshot(db_path: Path) -> dict[str, tuple | None]:
    return {
        "project": _fetch_one(db_path, "SELECT id, name, repo_path, notes FROM projects"),
        "session": _fetch_one(
            db_path, "SELECT id, project_id, task_id, agent_type, model_name FROM agent_sessions"
        ),
        "plan_item": _fetch_one(db_path, "SELECT id, item_key, title, description FROM plan_items"),
        "task": _fetch_one(db_path, "SELECT id, project_id, title, description FROM tasks"),
        "report": _fetch_one(db_path, "SELECT id, session_id, summary FROM agent_reports"),
        "binding": _fetch_one(db_path, "SELECT id, session_id, task_id FROM session_task_bindings"),
        "link": _fetch_one(
            db_path, "SELECT id, report_id, session_task_binding_id FROM agent_report_binding_links"
        ),
    }


def test_known_hybrid_db_repair_adds_schema_stamps_and_preserves_data(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    before = _snapshot(db_path)

    inspection = inspect_local_schema(db_path)
    assert inspection.state == SchemaState.KNOWN_REPAIRABLE_DRIFT

    result = repair_database(db_path)

    assert result.changed is True
    assert result.backup_path is not None
    assert (result.backup_path / "flowos.db").is_file()
    assert (result.backup_path / "metadata.json").is_file()
    assert inspect_local_schema(db_path).state == SchemaState.HEALTHY
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == ALEMBIC_HEAD
    assert before == _snapshot(db_path)
    assert _foreign_key_check(db_path) == []

    report_columns = _columns(db_path, "agent_reports")
    assert "report_type" in report_columns
    assert "work_status" in report_columns
    assert "source_report_id" in report_columns
    assert "source_path" in report_columns
    assert "source_content_sha256" in report_columns
    assert "workflow_ledger_events" in {
        row[0]
        for row in sqlite3.connect(str(db_path))
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    }
    assert "uq_plans_one_active_per_project" in _indexes(db_path, "plans")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with Session(engine) as session:
            assert session.query(AgentReport).first().id == "report-1"
            assert session.query(WorkflowLedgerEvent).count() == 0
    finally:
        engine.dispose()


def test_repair_is_idempotent_on_already_repaired_db(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    repair_database(db_path)
    before = _snapshot(db_path)

    result = repair_database(db_path)

    assert result.changed is False
    assert result.backup_path is None
    assert result.final_state == SchemaState.HEALTHY
    assert before == _snapshot(db_path)
    assert _indexes(db_path, "agent_reports").count("ix_agent_reports_source_path") == 1
    assert _indexes(db_path, "agent_reports").count("ix_agent_reports_source_report_id") == 1
    assert _indexes(db_path, "workflow_ledger_events").count("ix_workflow_ledger_source") == 1
    assert _indexes(db_path, "plans").count("uq_plans_one_active_per_project") == 1


def test_previous_head_repair_adds_active_index_without_changing_plan_rows(tmp_path: Path):
    db_path = tmp_path / "previous-head.db"
    _create_alembic_db(db_path, "b7c2e1d4a903")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO projects (id, name, repo_path, status, created_at) "
            "VALUES ('project-1', 'P', 'C:/p', 'ACTIVE', '2026-09-03')"
        )
        conn.execute(
            "INSERT INTO plans (id, project_id, title, status, created_at) "
            "VALUES ('plan-1', 'project-1', 'Plan', 'ACTIVE', '2026-09-03')"
        )
        conn.commit()
    finally:
        conn.close()

    assert inspect_local_schema(db_path).state == SchemaState.KNOWN_REPAIRABLE_DRIFT
    before = _fetch_one(db_path, "SELECT id, project_id, title, status FROM plans")

    result = repair_database(db_path)

    assert result.final_state == SchemaState.HEALTHY
    assert _fetch_one(db_path, "SELECT id, project_id, title, status FROM plans") == before
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == ALEMBIC_HEAD
    assert "uq_plans_one_active_per_project" in _indexes(db_path, "plans")


def test_previous_head_duplicate_active_plans_abort_repair_without_data_change(tmp_path: Path):
    db_path = tmp_path / "duplicate-active.db"
    _create_alembic_db(db_path, "b7c2e1d4a903")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO projects (id, name, repo_path, status, created_at) "
            "VALUES ('project-1', 'P', 'C:/p', 'ACTIVE', '2026-09-03')"
        )
        conn.executemany(
            "INSERT INTO plans (id, project_id, title, status, created_at) "
            "VALUES (?, 'project-1', ?, 'ACTIVE', '2026-09-03')",
            [("plan-1", "One"), ("plan-2", "Two")],
        )
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(str(db_path))
    try:
        before = conn.execute("SELECT id, status FROM plans ORDER BY id").fetchall()
    finally:
        conn.close()

    with pytest.raises(sqlite3.IntegrityError):
        repair_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT id, status FROM plans ORDER BY id").fetchall() == before
        assert (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "b7c2e1d4a903"
        )
        assert "uq_plans_one_active_per_project" not in {
            row[1] for row in conn.execute("PRAGMA index_list(plans)").fetchall()
        }
    finally:
        conn.close()


def test_unknown_alembic_version_with_valid_target_schema_is_unknown_and_refused(
    tmp_path: Path,
):
    db_path = tmp_path / "flowos.db"
    _create_fresh_alembic_head_db(db_path)
    _set_alembic_version(db_path, "z9future000x")
    before_snapshot = _snapshot(db_path)
    before_columns = _columns(db_path, "agent_reports")
    backups_dir = db_path.parent / "backups"

    inspection = inspect_local_schema(db_path)
    assert inspection.state == SchemaState.UNKNOWN_DRIFT
    assert inspection.alembic_version == "z9future000x"

    with pytest.raises(SchemaUnknownDriftError):
        repair_database(db_path)

    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == "z9future000x"
    assert _columns(db_path, "agent_reports") == before_columns
    assert _snapshot(db_path) == before_snapshot
    assert not backups_dir.exists()


def test_missing_alembic_version_known_hybrid_remains_repairable(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TABLE alembic_version")
        conn.commit()
    finally:
        conn.close()

    inspection = inspect_local_schema(db_path)

    assert inspection.alembic_version is None
    assert inspection.state == SchemaState.KNOWN_REPAIRABLE_DRIFT


def test_unknown_drift_refuses_without_schema_mutation_or_stamp(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("ALTER TABLE agent_reports ADD COLUMN source_path INTEGER")
        conn.commit()
    finally:
        conn.close()
    before_columns = _columns(db_path, "agent_reports")

    inspection = inspect_local_schema(db_path)
    assert inspection.state == SchemaState.UNKNOWN_DRIFT
    with pytest.raises(SchemaUnknownDriftError):
        repair_database(db_path)

    assert _columns(db_path, "agent_reports") == before_columns
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == "03de14cbf6aa"
    assert "workflow_ledger_events" not in _table_names(db_path)


def test_workflow_ledger_without_idempotency_unique_is_unknown_drift(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
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
    PRIMARY KEY (id)
)
"""
        )
        conn.commit()
    finally:
        conn.close()
    before_tables = _table_names(db_path)
    before_version = _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0]

    inspection = inspect_local_schema(db_path)
    assert inspection.state == SchemaState.UNKNOWN_DRIFT
    assert any("idempotency" in reason for reason in inspection.unknown_reasons)
    with pytest.raises(SchemaUnknownDriftError):
        repair_database(db_path)

    assert _table_names(db_path) == before_tables
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == before_version


def test_backup_failure_prevents_ddl_and_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    before_columns = _columns(db_path, "agent_reports")

    def _fail_backup(path: Path):  # noqa: ARG001
        raise SchemaBackupError("boom")

    import flowos.service.services.infrastructure.persistence.schema_repair as schema_repair

    monkeypatch.setattr(schema_repair, "create_schema_backup", _fail_backup)
    with pytest.raises(SchemaBackupError):
        schema_repair.repair_database(db_path)

    assert _columns(db_path, "agent_reports") == before_columns
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == "03de14cbf6aa"
    assert "workflow_ledger_events" not in _table_names(db_path)


def test_prestamp_failure_rolls_back_schema_data_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)
    before_snapshot = _snapshot(db_path)
    before_columns = _columns(db_path, "agent_reports")

    import flowos.service.services.infrastructure.persistence.schema_repair as schema_repair

    def _fail_prestamp(conn: sqlite3.Connection) -> None:  # noqa: ARG001
        raise RuntimeError("pre-stamp ORM-equivalent verification failed")

    monkeypatch.setattr(schema_repair, "_verify_required_column_selects", _fail_prestamp)
    with pytest.raises(RuntimeError, match="pre-stamp"):
        schema_repair.repair_database(db_path)

    assert _columns(db_path, "agent_reports") == before_columns
    assert "workflow_ledger_events" not in _table_names(db_path)
    assert _snapshot(db_path) == before_snapshot
    assert _fetch_one(db_path, "SELECT version_num FROM alembic_version")[0] == "03de14cbf6aa"


def test_startup_detection_blocks_known_drift_before_legacy_bootstrap(tmp_path: Path):
    db_path = tmp_path / "flowos.db"
    _create_known_hybrid_db(db_path)

    with pytest.raises(SchemaRepairRequiredError):
        _run_migrations(db_path)

    assert "report_type" not in _columns(db_path, "agent_reports")
    assert "workflow_ledger_events" not in _table_names(db_path)


def test_fresh_alembic_head_db_is_detected_as_healthy(tmp_path: Path):
    db_path = tmp_path / "fresh-head.db"
    _create_fresh_alembic_head_db(db_path)

    inspection = inspect_local_schema(db_path)
    assert inspection.state == SchemaState.HEALTHY
    assert inspection.alembic_version == ALEMBIC_HEAD


def _table_names(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
