"""HTTP kontroler za verifikaciju — Faza 3."""

from fastapi import APIRouter

router = APIRouter(prefix="/verification", tags=["verification"])


@router.get("")
async def verification_status():
    return {"status": "not_run"}
