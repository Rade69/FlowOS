"""API ugovori za konflikte."""

from datetime import datetime

from pydantic import BaseModel


class ConflictResponse(BaseModel):
    id: str
    project_id: str
    file_path: str
    session_ids: list[str]
    conflict_level: str  # HIGH, MEDIUM, INFO
    description: str
    detected_at: datetime
    acknowledged_at: datetime | None
