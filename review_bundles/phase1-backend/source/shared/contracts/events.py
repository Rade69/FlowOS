"""API ugovori za događaje sesije."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from flowos.shared.enums.event import EventType


class SessionEventCreate(BaseModel):
    event_type: str
    summary: str
    payload_json: str | None = None
    source: str = "WRAPPER"
    idempotency_key: str
    occurred_at: datetime | None = None

    @field_validator("event_type")
    @classmethod
    def event_type_valid(cls, v: str) -> str:
        try:
            EventType(v)
        except ValueError:
            raise ValueError(
                f"Neispravan event_type: '{v}'. "
                f"Dozvoljene vrednosti: {[e.value for e in EventType]}"
            )
        return v

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary ne sme biti prazan")
        return v.strip()

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("idempotency_key ne sme biti prazan")
        return v.strip()


class SessionEventResponse(BaseModel):
    id: str
    session_id: str
    event_type: str
    summary: str
    payload_json: str | None
    source: str
    idempotency_key: str | None
    occurred_at: datetime
