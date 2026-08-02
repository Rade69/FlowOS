"""HTTP kontroler za worktree operacije — Faza 4."""

from fastapi import APIRouter

router = APIRouter(prefix="/worktrees", tags=["worktrees"])


@router.get("")
async def list_worktrees(project_id: str | None = None):
    return {"worktrees": [], "project_id": project_id}
