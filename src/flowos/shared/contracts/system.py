"""API ugovori za sistemske endpoint-e: /health, /version, /runtime."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class VersionResponse(BaseModel):
    version: str
    api_version: int = 1


class RuntimeResponse(BaseModel):
    pid: int
    port: int
    started_at: str
    data_directory: str
