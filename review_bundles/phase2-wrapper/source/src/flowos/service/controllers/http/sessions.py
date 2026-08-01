"""HTTP API Controllers — Sesije."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.sessions.service import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


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
        "execution_mode": s.execution_mode, "terminal_label": s.terminal_label,
        "working_directory": s.working_directory, "repo_path": s.repo_path,
        "branch_name": s.branch_name, "worktree_path": s.worktree_path,
        "plan_item_id": getattr(s, "plan_item_id", None),
        "base_commit_sha": s.base_commit_sha, "pid": s.pid,
        "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "exit_code": s.exit_code,
    }


@router.post("")
def create_session(data: dict, session: Session = Depends(get_session)):
    svc = SessionService(session)
    s = svc.create_session(
        project_id=data["project_id"],
        agent_type=data["agent_type"],
        repo_path=data["repo_path"],
        task_id=data.get("task_id"),
        model_name=data.get("model_name"),
        execution_mode=data.get("execution_mode", "WRAPPED_TERMINAL"),
        branch_name=data.get("branch_name"),
        worktree_path=data.get("worktree_path"),
        plan_item_id=data.get("plan_item_id"),
        base_commit_sha=data.get("base_commit_sha"),
        pid=data.get("pid"),
    )
    session.commit()
    return _session_to_dict(s)


@router.get("/active")
def list_active_sessions(project_id: str, session: Session = Depends(get_session)):
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
def end_session(session_id: str, data: dict = {}, session: Session = Depends(get_session)):
    s = SessionService(session).end_session(
        session_id,
        exit_code=data.get("exit_code"),
        base_commit_sha=data.get("base_commit_sha"),
        status=data.get("status", "COMPLETED"),
    )
    if not s:
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    session.commit()
    return _session_to_dict(s)