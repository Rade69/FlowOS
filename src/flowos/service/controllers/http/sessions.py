"""HTTP API Controllers — Sesije (Pydantic ugovori)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.shared.contracts.sessions import (
    SessionTaskBindingResponse,
    SessionTaskBindingSwitchRequest,
)
from flowos.shared.enums.session import SessionTaskBindingSource

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


def get_session(request: Request) -> Session:  # type: ignore[misc]  # FastAPI generator dependency
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
        "id": s.id,
        "task_id": s.task_id,
        "project_id": s.project_id,
        "agent_type": s.agent_type,
        "model_name": s.model_name,
        "execution_mode": s.execution_mode,
        "repo_path": s.repo_path,
        "branch_name": s.branch_name,
        "worktree_path": s.worktree_path,
        "plan_item_id": getattr(s, "plan_item_id", None),
        "base_commit_sha": s.base_commit_sha,
        "pid": s.pid,
        "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "exit_code": s.exit_code,
    }


def _binding_to_response(binding: Any) -> SessionTaskBindingResponse:
    if binding.task_id:
        binding_kind = "TASK"
    elif binding.plan_item_id:
        binding_kind = "PLAN_ITEM"
    else:
        binding_kind = "UNASSIGNED"
    return SessionTaskBindingResponse(
        id=binding.id,
        session_id=binding.session_id,
        task_id=binding.task_id,
        plan_item_id=binding.plan_item_id,
        started_at=binding.started_at,
        ended_at=binding.ended_at,
        binding_source=SessionTaskBindingSource(binding.binding_source),
        binding_kind=binding_kind,
        is_active=binding.ended_at is None,
    )


@router.post("")
def create_session(data: SessionCreateRequest, session: Session = Depends(get_session)):
    svc = SessionService(session)
    s = svc.create_session(
        project_id=data.project_id,
        agent_type=data.agent_type,
        repo_path=data.repo_path,
        task_id=data.task_id,
        model_name=data.model_name,
        execution_mode=data.execution_mode,
        branch_name=data.branch_name,
        worktree_path=data.worktree_path,
        plan_item_id=data.plan_item_id,
        base_commit_sha=data.base_commit_sha,
        pid=data.pid,
    )
    return _session_to_dict(s)


@router.get("/{session_id}/bindings", response_model=list[SessionTaskBindingResponse])
def list_session_bindings(session_id: str, session: Session = Depends(get_session)):
    svc = SessionTaskBindingService(session)
    if not SessionService(session).get_session(session_id):
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    return [_binding_to_response(binding) for binding in svc.get_bindings(session_id)]


@router.post("/{session_id}/bindings/switch", response_model=SessionTaskBindingResponse)
def switch_session_binding(
    session_id: str,
    data: SessionTaskBindingSwitchRequest,
    session: Session = Depends(get_session),
):
    try:
        binding = SessionTaskBindingService(session).switch_binding(
            session_id,
            task_id=data.task_id,
            plan_item_id=data.plan_item_id,
            binding_source=SessionTaskBindingSource.USER,
        )
    except ValueError as e:
        message = str(e)
        if "ne postoji" in message:
            raise HTTPException(status_code=404, detail=message) from e
        raise HTTPException(status_code=409, detail=message) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=409,
            detail="Binding je u međuvremenu promijenjen. Osvježi stanje i pokušaj ponovo.",
        ) from e
    return _binding_to_response(binding)


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
def end_session(
    session_id: str, data: SessionEndRequest | None = None, session: Session = Depends(get_session)
):
    if data is None:
        data = SessionEndRequest()
    s = SessionService(session).end_session(
        session_id,
        exit_code=data.exit_code,
        result_commit_sha=data.result_commit_sha,
        status=data.status,
    )
    if not s:
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    return _session_to_dict(s)


@router.post("/{session_id}/heartbeat")
def session_heartbeat(session_id: str, session: Session = Depends(get_session)):
    """Procesni heartbeat — agent/proces potvrđuje da je živ.

    Nezavisan od filesystem aktivnosti. Poziva se periodično
    iz adaptera, wrapper-a ili process monitora.

    Heartbeat se odbija za sesije u terminalnom stanju (COMPLETED,
    ABANDONED, NEEDS_REVIEW) sa 409 Conflict.
    """
    try:
        s = SessionService(session).record_heartbeat(session_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if not s:
        raise HTTPException(status_code=404, detail="Sesija nije pronađena")
    return {"status": "ok", "session_id": session_id}
