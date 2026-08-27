"""FLOW-1109 REV-1109-H1 — worktree verify HTTP response redaction.

Dokazuje da POST /worktrees/{id}/verify vraća ``[REDACTED]`` umjesto poznatih
tajni u stdout/stderr, dok raw ``VerificationResult`` ostaje nepromijenjen.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flowos.service.controllers.http.worktrees import router as worktrees_router
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.redaction import (
    register_secret,
    reset_redactor,
)
from flowos.service.services.verification.service import VerificationResult

SECRET = "sk-http-test-secret-abcdef1234567890"


@pytest.fixture()
def engine():
    import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401

    eng = create_engine(
        "sqlite:///file:worktree_verify_redaction?mode=memory&cache=shared",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _pragma(dbapi_connection, _connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def client(engine):
    app = FastAPI(title="FlowOS Test")
    app.include_router(worktrees_router)
    app.state.session_factory = sessionmaker(bind=engine)
    return TestClient(app)


def _verify_result() -> VerificationResult:
    return VerificationResult(
        artifact_id="art-http",
        verify_path="scripts/verify.py",
        success=True,
        exit_code=0,
        stdout=f"before {SECRET} after {SECRET}",
        stderr=f"err {SECRET}",
        duration_seconds=1.0,
        timed_out=False,
        verified_at="2026-08-19T00:00:00Z",
    )


def test_worktree_verify_rediguje_stdout_stderr(client) -> None:
    result = _verify_result()
    register_secret(SECRET)
    try:
        with (
            patch(
                "flowos.service.services.worktrees.manager.WorktreeManager.get_worktree",
                return_value={"worktree_path": "C:/test/repo"},
            ),
            patch(
                "flowos.service.services.verification.service.VerificationService.run_verify",
                return_value=result,
            ),
        ):
            response = client.post("/worktrees/wt-1/verify")
    finally:
        reset_redactor()

    assert response.status_code == 200
    body = response.json()
    assert SECRET not in response.text
    assert "[REDACTED]" in body["stdout"]
    assert "[REDACTED]" in body["stderr"]
    # Non-secret polja ostaju nepromijenjena.
    assert body["exit_code"] == 0
    assert body["success"] is True
    assert body["artifact_id"] == "art-http"
    assert body["duration_seconds"] == 1.0
    # Raw verification result (in-memory computation data) nije mutiran.
    assert SECRET in result.stdout
    assert SECRET in result.stderr
