"""API ugovori za sesije."""

from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    task_id: str | None = None
    project_id: str
    agent_type: str
    model_name: str | None = None
    execution_mode: str = "WRAPPED_TERMINAL"
    terminal_label: str | None = None
    working_directory: str | None = None
    repo_path: str
    branch_name: str | None = None
    worktree_path: str | None = None
    hint_glob: str | None = None
    idempotency_key: str


class SessionUpdate(BaseModel):
    task_id: str | None = None
    status: str | None = None
    terminal_label: str | None = None
    hint_glob: str | None = None


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
