"""API ugovori za projekte."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    repo_path: str
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ime projekta ne sme biti prazno")
        if len(stripped) > 200:
            raise ValueError("Ime projekta sme imati najviše 200 karaktera")
        return stripped

    @field_validator("repo_path")
    @classmethod
    def repo_path_valid(cls, v: str) -> str:
        p = Path(v.strip())
        if not p.is_absolute():
            raise ValueError(f"repo_path mora biti apsolutna putanja: {v}")
        return str(p)


class ProjectUpdate(BaseModel):
    name: str | None = None
    repo_path: str | None = None
    notes: str | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Ime projekta ne sme biti prazno")
            if len(stripped) > 200:
                raise ValueError("Ime projekta sme imati najviše 200 karaktera")
            return stripped
        return v

    @field_validator("repo_path")
    @classmethod
    def repo_path_valid(cls, v: str | None) -> str | None:
        if v is not None:
            p = Path(v.strip())
            if not p.is_absolute():
                raise ValueError(f"repo_path mora biti apsolutna putanja: {v}")
            return str(p)
        return v


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_path: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
