"""API ugovori za sesije."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, field_validator

from flowos.shared.enums.session import ExecutionMode, SessionStatus


class SessionCreate(BaseModel):
    task_id: str | None = None
    project_id: str
    agent_type: str
    model_name: str | None = None
    execution_mode: str = ExecutionMode.WRAPPED_TERMINAL.value
    terminal_label: str | None = None
    working_directory: str | None = None
    repo_path: str
    branch_name: str | None = None
    worktree_path: str | None = None
    hint_glob: str | None = None
    idempotency_key: str

    @field_validator("project_id")
    @classmethod
    def project_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_id ne sme biti prazan")
        return v.strip()

    @field_validator("agent_type")
    @classmethod
    def agent_type_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("agent_type ne sme biti prazan")
        return stripped

    @field_validator("execution_mode")
    @classmethod
    def execution_mode_valid(cls, v: str) -> str:
        try:
            ExecutionMode(v)
        except ValueError:
            raise ValueError(
                f"Neispravan execution_mode: '{v}'. "
                f"Dozvoljene vrednosti: {[e.value for e in ExecutionMode]}"
            )
        return v

    @field_validator("repo_path")
    @classmethod
    def repo_path_valid(cls, v: str) -> str:
        p = Path(v.strip())
        if not p.is_absolute():
            raise ValueError(f"repo_path mora biti apsolutna putanja: {v}")
        return str(p)

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("idempotency_key ne sme biti prazan")
        return v.strip()


class SessionUpdate(BaseModel):
    task_id: str | None = None
    status: str | None = None
    terminal_label: str | None = None
    hint_glob: str | None = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                SessionStatus(v)
            except ValueError:
                raise ValueError(
                    f"Neispravan status: '{v}'. "
                    f"Dozvoljene vrednosti: {[e.value for e in SessionStatus]}"
                )
        return v


class SessionResponse(BaseModel):
    id: str
    task_id: str | None
    project_id: str
    agent_type: str
    model_name: str | None
    execution_mode: str
    terminal_label: str | None
    working_directory: str | None
    repo_path: str
    branch_name: str | None
    worktree_path: str | None
    base_commit_sha: str | None
    pid: int | None
    status: str
    started_at: datetime | None
    last_activity_at: datetime | None
    ended_at: datetime | None
    exit_code: int | None
