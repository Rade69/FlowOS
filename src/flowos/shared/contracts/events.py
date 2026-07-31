"""API ugovori za događaje sesije."""

from datetime import datetime

from pydantic import BaseModel


class SessionEventCreate(BaseModel):
    event_type: str
    summary: str
    payload_json: str | None = None
    source: str = "WRAPPER"
    idempotency_key: str
    occurred_at: datetime | None = None


class SessionEventResponse(BaseModel):
    id: str
    session_id: str
    event_type: str
    summary: str
    payload_json: str | None
    source: str
    idempotency_key: str | None
    occurred_at: datetime
