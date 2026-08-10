"""HTTP API Controllers — Projekti (CRUD).

Tanke rute sa Pydantic request/response modelima.
Bez ORM importa, bez ručnih dict-ova.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.projects.service import ProjectService
from flowos.shared.contracts.projects import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["Projects"])


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


def _project_to_response(p) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        repo_path=p.repo_path,
        status=p.status,
        notes=p.notes,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(session: Session = Depends(get_session)):
    return [_project_to_response(p) for p in ProjectService(session).list_projects()]


@router.post("", response_model=ProjectResponse)
def create_project(data: ProjectCreate, session: Session = Depends(get_session)):
    svc = ProjectService(session)
    p = svc.create_project(name=data.name, repo_path=data.repo_path, notes=data.notes)
    session.commit()
    return _project_to_response(p)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, session: Session = Depends(get_session)):
    p = ProjectService(session).get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    return _project_to_response(p)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, data: ProjectUpdate, session: Session = Depends(get_session)):
    p = ProjectService(session).update_project(
        project_id,
        name=data.name,
        repo_path=data.repo_path,
        notes=data.notes,
        status=data.status,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    session.commit()
    return _project_to_response(p)


@router.delete("/{project_id}")
def delete_project(project_id: str, session: Session = Depends(get_session)):
    ok = ProjectService(session).delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    session.commit()
    return {"status": "deleted", "id": project_id}


@router.get("/{project_id}/timeline")
def get_project_timeline(project_id: str, limit: int = 30, session: Session = Depends(get_session)):
    """Vraća nedavne događaje za projekat (FileActivity + SessionEvents)."""
    from flowos.service.services.project_timeline import ProjectTimelineService

    return ProjectTimelineService(session).get_timeline(project_id, limit=limit)


@router.get("/{project_id}/state")
def get_project_state(project_id: str, session: Session = Depends(get_session)):
    """Vraća jedinstveno stanje projekta iz svih izvora."""
    from flowos.service.services.project_state import ProjectStateService

    svc = ProjectStateService(session)
    return svc.get_state(project_id)
