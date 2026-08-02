"""HTTP kontroler za izvještaje — Faza 3."""

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def list_reports(session_id: str | None = None):
    return {"reports": [], "session_id": session_id}
