"""HTTP API Controllers — Sesije (Pydantic ugovori)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from flowos.service.services.sessions.service import SessionService
from flowos.shared.enums.session import SessionStatus

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class SessionCreateRequest(BaseModel):
    project_id: str
    agent_type: str
    repo_path: str
    task_id: str | None = None
    model_name: str | None = None
    execution_mode: str = "WRAPPED_TERMINAL"
    branch_name: str | None = None
    worktree_path: str | None = None
    plan_item_id: str | None = None
    base_commit_sha: str | None = None
    pid: int | None = None


class SessionEndRequest(BaseModel):
    exit_code: int | None = None
    result_commit_sha: str | None = None
    status: str = "COMPLETED"


def get_session(request: Request) -> Session:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _session_to_dict(s) -> dict:
    return {
        "id": s.id, "task_id": s.task_id, "project_id": s.project_id,
        "agent_type": s.agent_type, "model_name": s.model_name,
        "execution_mode": s.execution_mode,
        "repo_path": s.repo_path, "branch_name": s.branch_name,
        "worktree_path": s.worktree_path,
        "plan_item_id": getattr(s, "plan_item_id", None),
        "base_commit_sha": s.base_commit_sha,
        "pid": s.pid, "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "exit_code": s.exit_code,
    }


@router.post("")
def create_session(data: SessionCreateRequest, session: Session = Depends(get_session)):
    svc = SessionService(session)
    s = svc.create_session(
        project_id=data.project_id, agent_type=data.agent_type,
        repo_path=data.repo_path, task_id=data.task_id,
        model_name=data.model_name, execution_mode=data.execution_mode,
        branch_name=data.branch_name, worktree_path=data.worktree_path,
        plan_item_id=data.plan_item_id,
        base_commit_sha=data.base_commit_sha, pid=data.pid,
    )
    return _session_to_dict(s)


@router.get("/active")
def list_active(project_id: str, session: Session = Depends(get_session)):
    return [_session_to_dict(s) for s in SessionService(session).list_active_sessions(project_id)]


@router.get("")
def list_sessions(project_id: str, limit: int = 50, session: Session = Depends(get_session)):
    return [_session_to_dict(s) for s in SessionService(session).list_sessions(project_id, limit)]


@router.get("/{session_id}")
def get_session_endpoint(session_id: str, session: Session = Depends(get_session)):
    s = SessionService(session).get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    return _session_to_dict(s)


@router.post("/{session_id}/end")
def end_session(session_id: str, data: SessionEndRequest | None = None, session: Session = Depends(get_session)):
    if data is None:
        data = SessionEndRequest()
    s = SessionService(session).end_session(
        session_id, exit_code=data.exit_code,
        result_commit_sha=data.result_commit_sha, status=data.status,
    )
    if not s:
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    return _session_to_dict(s)