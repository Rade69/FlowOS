"""FLOW-1109 — integracioni testovi log/artifact redaction boundary.

Dokazuje da poznata tajna (npr. runtime bearer token) ne završava u
FlowOS-owned log fajlu niti u FlowOS-generated verification artifactu —
SECRET BEFORE BOUNDARY → [REDACTED] AFTER BOUNDARY.
"""

from __future__ import annotations

import logging

import pytest

from flowos.service.services.infrastructure.logging import setup_logging
from flowos.service.services.infrastructure.redaction import (
    REDACTED,
    register_secret,
    reset_redactor,
)
from flowos.service.services.verification.service import ArtifactStore

SECRET = "flowos-test-token-abcdef1234567890"


@pytest.fixture()
def registered_secret():
    register_secret(SECRET)
    yield SECRET
    reset_redactor()


@pytest.fixture()
def flowos_logger(tmp_path):
    logger = setup_logging(level=logging.INFO, log_dir=tmp_path, console=False)
    yield logger, tmp_path / "flowos-service.log"
    root = logging.getLogger("flowos")
    root.handlers.clear()


def _flush_and_read(log_path):
    for handler in logging.getLogger("flowos").handlers:
        handler.flush()
    return log_path.read_text(encoding="utf-8")


def test_log_persistence_boundary_rediguje_secret(registered_secret, flowos_logger) -> None:
    logger, log_path = flowos_logger
    logger.info("Authorization: Bearer %s", registered_secret)

    persisted = _flush_and_read(log_path)
    assert registered_secret not in persisted
    assert REDACTED in persisted


def test_exception_traceback_redigovan(registered_secret, flowos_logger) -> None:
    logger, log_path = flowos_logger
    try:
        raise ValueError(f"request failed token={registered_secret}")
    except ValueError:
        logger.exception("handling error")

    persisted = _flush_and_read(log_path)
    assert registered_secret not in persisted
    assert REDACTED in persisted


def test_verification_artifact_rediguje_stdout_stderr_command(registered_secret, tmp_path) -> None:
    store = ArtifactStore(base_path=str(tmp_path))
    store.save(
        verification_id="v1",
        command=f"python verify.py --token {registered_secret}",
        stdout=f"stdout sa tajnom: {registered_secret}",
        stderr=f"stderr sa tajnom: {registered_secret}",
        exit_code=0,
        duration_seconds=0.0,
        started_at="2026-08-18T00:00:00Z",
        finished_at="2026-08-18T00:00:00Z",
    )

    base = tmp_path / "verification" / "v1"
    stdout_text = (base / "stdout.txt").read_text(encoding="utf-8")
    stderr_text = (base / "stderr.txt").read_text(encoding="utf-8")
    command_text = (base / "command.txt").read_text(encoding="utf-8")

    assert registered_secret not in stdout_text
    assert registered_secret not in stderr_text
    assert registered_secret not in command_text
    assert REDACTED in stdout_text
    assert REDACTED in stderr_text
    assert REDACTED in command_text
