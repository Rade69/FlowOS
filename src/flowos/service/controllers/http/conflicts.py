"""HTTP kontroler za konflikte — Faza 3."""

from fastapi import APIRouter

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("")
async def list_conflicts(project_id: str | None = None):
    return {"conflicts": [], "project_id": project_id}
