"""HTTP API Controllers — Project Resume (Gde si stao)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.resume_models import (
    ExternalActivity,
    ProjectWorkspaceState,
)
from flowos.service.services.project_resume import ProjectResumeService

router = APIRouter(prefix="/projects", tags=["Project Resume"])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


# ═══════════════════════════════════════════════════════════════════
# Resume
# ═══════════════════════════════════════════════════════════════════


@router.get("/{project_id}/resume")
def get_resume(project_id: str, session: Session = Depends(get_session)):
    """Vraća 'Gde si stao' sažetak za projekat."""
    svc = ProjectResumeService(session)
    resume = svc.regenerate(project_id)
    session.commit()
    return _resume_to_dict(resume)


@router.post("/{project_id}/resume/regenerate")
def regenerate_resume(project_id: str, session: Session = Depends(get_session)):
    """Regeneriše 'Gde si stao' sažetak iz trajnih izvora."""
    svc = ProjectResumeService(session)
    resume = svc.regenerate(project_id)
    session.commit()
    return _resume_to_dict(resume)


# ═══════════════════════════════════════════════════════════════════
# Workspace state (read-only)
# ═══════════════════════════════════════════════════════════════════


@router.get("/{project_id}/workspace-state")
def get_workspace_state(project_id: str, session: Session = Depends(get_session)):
    """Vraća poslednje poznato Git stanje projekta."""
    ws = (
        session.query(ProjectWorkspaceState)
        .filter(ProjectWorkspaceState.project_id == project_id)
        .first()
    )
    if not ws:
        return {"status": "NO_HISTORY"}
    return {
        "id": ws.id,
        "project_id": ws.project_id,
        "last_known_commit_sha": ws.last_known_commit_sha,
        "last_known_branch": ws.last_known_branch,
        "reconciliation_status": ws.reconciliation_status,
        "external_change_summary": ws.external_change_summary,
        "last_observed_at": ws.last_observed_at.isoformat() if ws.last_observed_at else None,
        "last_reconciled_at": ws.last_reconciled_at.isoformat() if ws.last_reconciled_at else None,
    }


# ═══════════════════════════════════════════════════════════════════
# External activity
# ═══════════════════════════════════════════════════════════════════


@router.post("/{project_id}/external-activity")
def create_external_activity(project_id: str, data: dict, session: Session = Depends(get_session)):
    """Beleži aktivnost van FlowOS-a."""
    activity = ExternalActivity(
        project_id=project_id,
        plan_item_id=data.get("plan_item_id"),
        task_id=data.get("task_id"),
        source=data.get("source", "UNKNOWN"),
        summary=data.get("summary", "Nepoznata eksterna izmena"),
        commit_shas_json=data.get("commit_shas_json"),
        changed_files_json=data.get("changed_files_json"),
        user_note=data.get("user_note"),
    )
    session.add(activity)
    session.commit()
    return {
        "id": activity.id,
        "project_id": activity.project_id,
        "source": activity.source,
        "summary": activity.summary,
        "attribution": activity.attribution,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


@router.get("/{project_id}/external-activity")
def list_external_activity(project_id: str, session: Session = Depends(get_session)):
    """Vraća sve zabeležene eksterne aktivnosti za projekat."""
    activities = (
        session.query(ExternalActivity)
        .filter(ExternalActivity.project_id == project_id)
        .order_by(ExternalActivity.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": a.id,
            "source": a.source,
            "summary": a.summary,
            "attribution": a.attribution,
            "user_note": a.user_note,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]


# ═══════════════════════════════════════════════════════════════════


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
