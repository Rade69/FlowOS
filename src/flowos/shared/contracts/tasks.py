"""API ugovori za zadatke."""

from datetime import datetime

from pydantic import BaseModel


class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    priority: str = "NORMAL"


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime | None
    done_at: datetime | None
