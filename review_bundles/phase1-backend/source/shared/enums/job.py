"""Statusi poslova, workflow tipovi i nivoi rizika (faza 6+)."""

from enum import StrEnum


class WorkflowType(StrEnum):
    CODING = "CODING"
    REVIEW = "REVIEW"
    PROBE = "PROBE"


class JobStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
