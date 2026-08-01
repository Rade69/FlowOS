"""Standardni API error response model.

Sve API greške koriste ovaj format:
{
    "code": "VALIDATION_ERROR",
    "message": "Nedostaje obavezno polje 'name'.",
    "details": {"field": "name"},
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
"""

import uuid

from pydantic import BaseModel, Field


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
