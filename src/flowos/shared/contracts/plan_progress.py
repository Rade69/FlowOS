"""API ugovori za planove, stavke, kriterijume i progres."""

from datetime import datetime

from pydantic import BaseModel, field_validator


# ═══════════════════════════════════════════════════════════════════
# Plan
# ═══════════════════════════════════════════════════════════════════


class PlanResponse(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    activated_at: datetime | None
    created_at: datetime


class PlanPhaseResponse(BaseModel):
    id: str
    plan_id: str
    phase_key: str
    title: str
    sequence: int
    status: str


class PlanProgressSummary(BaseModel):
    plan: PlanResponse | None
    phases: list[PlanPhaseResponse]
    total_items: int
    completed_items: int
    blocked_items: int


# ═══════════════════════════════════════════════════════════════════
# PlanItem
# ═══════════════════════════════════════════════════════════════════


class PlanItemResponse(BaseModel):
    id: str
    plan_phase_id: str
    item_key: str
    title: str
    description: str | None
    sequence: int
    risk_level: str
    status: str
    progress_source: str
    started_at: datetime | None
    implemented_at: datetime | None
    verified_at: datetime | None
    accepted_at: datetime | None
    blocked_reason: str | None
    created_at: datetime


class PlanItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    risk_level: str | None = None

    @field_validator("risk_level")
    @classmethod
    def risk_level_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError(f"Neispravan risk_level: '{v}'")
        return v


class StatusActionRequest(BaseModel):
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Razlog ne sme biti prazan")
        return v.strip() if v else None


# ═══════════════════════════════════════════════════════════════════
# PlanItemCriterion
# ═══════════════════════════════════════════════════════════════════


class PlanItemCriterionResponse(BaseModel):
    id: str
    plan_item_id: str
    criterion_key: str
    description: str
    status: str
    evidence_artifact_id: str | None
    verification_summary: str | None
    verified_at: datetime | None
    verified_by: str | None


class PlanItemCriterionUpdate(BaseModel):
    status: str | None = None
    evidence_artifact_id: str | None = None
    verification_summary: str | None = None
    verified_by: str | None = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {
                "PENDING",
                "IN_PROGRESS",
                "PASSED",
                "FAILED",
                "NOT_APPLICABLE",
                "NEEDS_REVIEW",
            }
            if v not in allowed:
                raise ValueError(
                    f"Neispravan status kriterijuma: '{v}'. Dozvoljene: {sorted(allowed)}"
                )
        return v


# ═══════════════════════════════════════════════════════════════════
# PlanProgressEvent
# ═══════════════════════════════════════════════════════════════════


class PlanProgressEventResponse(BaseModel):
    id: str
    plan_item_id: str
    session_id: str | None
    agent_report_id: str | None
    from_status: str
    to_status: str
    reason: str | None
    evidence_artifact_ids_json: str | None
    source: str
    occurred_at: datetime


# ═══════════════════════════════════════════════════════════════════
# PlanImport
# ═══════════════════════════════════════════════════════════════════


class PlanImportRequest(BaseModel):
    markdown_text: str
    source_artifact_id: str | None = None


class PlanImportResponse(BaseModel):
    plan_id: str
    phases: int
    items: int
    criteria: int
    dependencies: int
    unclear_count: int
    unclear_sections: list[str]


class PlanActivateRequest(BaseModel):
    pass  # Samo explicit POST zahteva potvrdu
