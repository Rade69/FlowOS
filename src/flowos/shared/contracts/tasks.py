"""API ugovori za zadatke."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from flowos.shared.enums.task import Priority, TaskStatus


class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    priority: str = Priority.NORMAL.value

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Naslov zadatka ne sme biti prazan")
        if len(stripped) > 500:
            raise ValueError("Naslov zadatka sme imati najviše 500 karaktera")
        return stripped

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: str) -> str:
        try:
            Priority(v)
        except ValueError:
            raise ValueError(
                f"Neispravan prioritet: '{v}'. Dozvoljene vrednosti: {[e.value for e in Priority]}"
            )
        return v

    @field_validator("project_id")
    @classmethod
    def project_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_id ne sme biti prazan")
        return v.strip()


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Naslov zadatka ne sme biti prazan")
            if len(stripped) > 500:
                raise ValueError("Naslov zadatka sme imati najviše 500 karaktera")
            return stripped
        return v

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                Priority(v)
            except ValueError:
                raise ValueError(
                    f"Neispravan prioritet: '{v}'. Dozvoljene vrednosti: {[e.value for e in Priority]}"
                )
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                TaskStatus(v)
            except ValueError:
                raise ValueError(
                    f"Neispravan status: '{v}'. Dozvoljene vrednosti: {[e.value for e in TaskStatus]}"
                )
        return v


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None
    status: str
    priority: str
    # FLOW-1202A: eksplicitno polje — GUI mora razlikovati linked od unassigned.
    plan_item_id: str | None = None
    created_at: datetime
    updated_at: datetime | None
    done_at: datetime | None
