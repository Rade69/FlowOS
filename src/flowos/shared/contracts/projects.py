"""API ugovori za projekte."""

from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    repo_path: str
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    repo_path: str | None = None
    notes: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_path: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
