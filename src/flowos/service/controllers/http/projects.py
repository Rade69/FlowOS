"""HTTP API Controllers — Projekti (CRUD)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _project_to_dict(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "repo_path": p.repo_path,
        "status": p.status,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
def list_projects(session: Session = Depends(get_session)):
    svc = ProjectService(session)
    projects = svc.list_projects()
    return [_project_to_dict(p) for p in projects]


@router.post("")
def create_project(data: dict, session: Session = Depends(get_session)):
    from flowos.shared.contracts.projects import ProjectCreate

    try:
        validated = ProjectCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    svc = ProjectService(session)
    p = svc.create_project(
        name=validated.name,
        repo_path=validated.repo_path,
        notes=validated.notes,
    )
    session.commit()
    return _project_to_dict(p)


@router.get("/{project_id}")
def get_project(project_id: str, session: Session = Depends(get_session)):
    svc = ProjectService(session)
    p = svc.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    return _project_to_dict(p)


@router.patch("/{project_id}")
def update_project(project_id: str, data: dict, session: Session = Depends(get_session)):
    svc = ProjectService(session)
    p = svc.update_project(
        project_id,
        name=data.get("name"),
        repo_path=data.get("repo_path"),
        notes=data.get("notes"),
        status=data.get("status"),
    )
    if not p:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    session.commit()
    return _project_to_dict(p)


@router.delete("/{project_id}")
def delete_project(project_id: str, session: Session = Depends(get_session)):
    svc = ProjectService(session)
    ok = svc.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen")
    session.commit()
    return {"status": "deleted", "id": project_id}
