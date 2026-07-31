"""Standardni API error response model."""

from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    correlation_id: str | None = None
