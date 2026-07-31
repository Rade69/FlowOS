"""Tipovi promene fajla i atribucije."""

from enum import StrEnum


class ChangeType(StrEnum):
    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


class Attribution(StrEnum):
    WORKTREE = "WORKTREE"
    SOLE_ACTIVE = "SOLE_ACTIVE"
    HINT = "HINT"
    UNATTRIBUTED = "UNATTRIBUTED"
    USER = "USER"
