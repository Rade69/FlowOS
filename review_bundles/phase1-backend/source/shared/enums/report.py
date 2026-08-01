"""Verdicti korisnika za izveštaje."""

from enum import StrEnum


class UserVerdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    NEEDS_WORK = "NEEDS_WORK"
    REJECTED = "REJECTED"
