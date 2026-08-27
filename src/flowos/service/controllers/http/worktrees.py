"""HTTP API Controllers — Worktree rute."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.redaction import redact_text
from flowos.service.services.worktrees.manager import WorktreeManager
from flowos.service.services.worktrees.service import (
    WorktreeError,
    WorktreeExistsError,
)

router = APIRouter(prefix="/worktrees", tags=["Worktrees"])


class WorktreeCreateRequest(BaseModel):
    project_id: str
    task_id: str
    slug: str = ""
    base_branch: str = ""
    retention_days: int = 7


class WorktreeCleanupRequest(BaseModel):
    force: bool = False


def get_session(request: Request) -> Session:  # type: ignore[misc]
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("")
def create_worktree(data: WorktreeCreateRequest, session: Session = Depends(get_session)):
    """Kreira novi worktree za zadatak."""
    mgr = WorktreeManager(session)
    try:
        return mgr.create_worktree(
            project_id=data.project_id,
            task_id=data.task_id,
            slug=data.slug,
            base_branch=data.base_branch,
            retention_days=data.retention_days,
        )
    except WorktreeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except WorktreeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("")
def list_worktrees(
    project_id: str = Query(...),
    flowos_only: bool = True,
    session: Session = Depends(get_session),
):
    """Lista worktree-ja za projekat."""
    mgr = WorktreeManager(session)
    try:
        return mgr.list_worktrees(project_id, flowos_only=flowos_only)
    except WorktreeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{worktree_id}")
def get_worktree(worktree_id: str, session: Session = Depends(get_session)):
    """Status worktree-ja."""
    mgr = WorktreeManager(session)
    result = mgr.get_worktree(worktree_id)
    if not result:
        raise HTTPException(status_code=404, detail="Worktree nije pronađen")
    return result


@router.post("/{worktree_id}/cleanup")
def cleanup_worktree(
    worktree_id: str,
    data: WorktreeCleanupRequest | None = None,
    session: Session = Depends(get_session),
):
    """Uklanja worktree uz retention proveru."""
    if data is None:
        data = WorktreeCleanupRequest()

    mgr = WorktreeManager(session)
    try:
        return mgr.cleanup_worktree(worktree_id, force=data.force)
    except WorktreeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{worktree_id}/integrate/prepare")
def prepare_integration(
    worktree_id: str,
    base_branch: str = Query("main"),
    session: Session = Depends(get_session),
):
    """Priprema integraciju: diff, changed files, conflict check."""
    mgr = WorktreeManager(session)
    try:
        return mgr.prepare_integration(worktree_id, base_branch=base_branch)
    except WorktreeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{worktree_id}/verify")
def verify_worktree(worktree_id: str, session: Session = Depends(get_session)):
    """Pokreće verify.py u worktree-ju."""

    from flowos.service.services.verification.service import VerificationService

    mgr = WorktreeManager(session)
    wt = mgr.get_worktree(worktree_id)
    if not wt:
        raise HTTPException(status_code=404, detail="Worktree nije pronađen")

    verify_svc = VerificationService()
    result = verify_svc.run_verify(wt["worktree_path"])
    return {
        "artifact_id": result.artifact_id,
        "exit_code": result.exit_code,
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "stdout": redact_text(result.stdout)[:1000],
        "stderr": redact_text(result.stderr)[:1000],
    }
