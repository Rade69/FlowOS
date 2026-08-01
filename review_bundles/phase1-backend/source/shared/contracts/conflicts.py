"""API ugovori za konflikte."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class ConflictResponse(BaseModel):
    id: str
    project_id: str
    file_path: str
    session_ids: list[str]
    conflict_level: str  # HIGH, MEDIUM, INFO
    description: str
    detected_at: datetime
    acknowledged_at: datetime | None = None

    @field_validator("conflict_level")
    @classmethod
    def conflict_level_valid(cls, v: str) -> str:
        allowed = {"HIGH", "MEDIUM", "INFO"}
        if v not in allowed:
            raise ValueError(
                f"Neispravan conflict_level: '{v}'. Dozvoljene vrednosti: {sorted(allowed)}"
            )
        return v
