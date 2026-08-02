"""HTTP API Controllers — Project Resume (Gde si stao).

Tanke rute — samo DTO → Service → DTO. Bez ORM importa.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from flowos.service.services.project_resume import ProjectResumeService

router = APIRouter(prefix="/projects", tags=["Project Resume"])


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


# ═══════════════════════════════════════════════════════════════════


@router.get("/{project_id}/resume")
def get_resume(project_id: str, session: Session = Depends(get_session)):
    """Vraća 'Gde si stao' sažetak (read-only, bez regeneracije)."""
    svc = ProjectResumeService(session)
    resume = svc.get_current_resume(project_id)
    if not resume:
        return {"resume_status": "NO_HISTORY", "confidence": "LOW"}
    return _resume_to_dict(resume)


@router.post("/{project_id}/resume/regenerate")
def regenerate_resume(project_id: str, session: Session = Depends(get_session)):
    """Regeneriše 'Gde si stao' sažetak iz trajnih izvora."""
    svc = ProjectResumeService(session)
    resume = svc.regenerate(project_id)
    return _resume_to_dict(resume)


@router.get("/{project_id}/workspace-state")
def get_workspace_state(project_id: str, session: Session = Depends(get_session)):
    svc = ProjectResumeService(session)
    ws = svc.get_workspace_state(project_id)
    if not ws:
        return {"status": "NO_HISTORY"}
    return ws


@router.get("/{project_id}/external-activity")
def list_external_activity(project_id: str, session: Session = Depends(get_session)):
    svc = ProjectResumeService(session)
    return svc.list_external_activities(project_id)


@router.post("/{project_id}/external-activity")
def create_external_activity(project_id: str, data: dict, session: Session = Depends(get_session)):
    svc = ProjectResumeService(session)
    return svc.create_external_activity(project_id, data)


def _resume_to_dict(r) -> dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "active_plan_id": r.active_plan_id,
        "last_plan_item_id": r.last_plan_item_id,
        "last_task_id": r.last_task_id,
        "last_session_id": r.last_session_id,
        "last_report_id": r.last_report_id,
        "last_commit_sha": r.last_commit_sha,
        "last_activity_at": r.last_activity_at.isoformat() if r.last_activity_at else None,
        "resume_status": r.resume_status,
        "where_stopped": r.where_stopped,
        "next_concrete_step": r.next_concrete_step,
        "resume_preconditions": r.resume_preconditions,
        "open_blockers_json": r.open_blockers_json,
        "open_decisions_json": r.open_decisions_json,
        "confidence": r.confidence,
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
    }
