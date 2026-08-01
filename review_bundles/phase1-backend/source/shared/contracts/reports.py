"""API ugovori za izveštaje."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from flowos.shared.enums.report import UserVerdict


class ReportUpdate(BaseModel):
    user_verdict: str | None = None  # ACCEPTED | NEEDS_WORK | REJECTED
    notes: str | None = None

    @field_validator("user_verdict")
    @classmethod
    def user_verdict_valid(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                UserVerdict(v)
            except ValueError:
                raise ValueError(
                    f"Neispravan user_verdict: '{v}'. "
                    f"Dozvoljene vrednosti: {[e.value for e in UserVerdict]}"
                )
        return v


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
