"""Režimi i statusi sesije."""

from enum import StrEnum


class ExecutionMode(StrEnum):
    WRAPPED_TERMINAL = "WRAPPED_TERMINAL"
    EXTERNAL_TRACKED = "EXTERNAL_TRACKED"
    MANAGED = "MANAGED"
    DURABLE = "DURABLE"


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
