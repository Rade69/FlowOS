"""API ugovori za izveštaje."""

from datetime import datetime

from pydantic import BaseModel


class ReportUpdate(BaseModel):
    user_verdict: str | None = None  # ACCEPTED | NEEDS_WORK | REJECTED
    notes: str | None = None


class ReportResponse(BaseModel):
    id: str
    session_id: str
    status: str
    summary: str | None
    changed_files: list[str] | None
    commit_shas: list[str] | None
    verification_summary: str | None
    open_risks: str | None
    user_verdict: str | None
    created_at: datetime
