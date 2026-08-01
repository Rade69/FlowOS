"""HTTP API Controllers — Zadaci (CRUD)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


def _task_to_dict(t) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "plan_item_id": t.plan_item_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "done_at": t.done_at.isoformat() if t.done_at else None,
    }


@router.get("")
def list_tasks(project_id: str, session: Session = Depends(get_session)):
    svc = TaskService(session)
    tasks = svc.list_tasks(project_id)
    return [_task_to_dict(t) for t in tasks]


@router.post("")
def create_task(data: dict, session: Session = Depends(get_session)):
    from flowos.shared.contracts.tasks import TaskCreate

    try:
        validated = TaskCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    svc = TaskService(session)
    t = svc.create_task(
        project_id=validated.project_id,
        title=validated.title,
        description=validated.description,
        priority=validated.priority,
    )
    session.commit()
    return _task_to_dict(t)


@router.get("/{task_id}")
def get_task(task_id: str, session: Session = Depends(get_session)):
    svc = TaskService(session)
    t = svc.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    return _task_to_dict(t)


@router.patch("/{task_id}")
def update_task(task_id: str, data: dict, session: Session = Depends(get_session)):
    svc = TaskService(session)
    t = svc.update_task(
        task_id,
        title=data.get("title"),
        description=data.get("description"),
        status=data.get("status"),
        priority=data.get("priority"),
        plan_item_id=data.get("plan_item_id"),
    )
    if not t:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    session.commit()
    return _task_to_dict(t)


@router.delete("/{task_id}")
def delete_task(task_id: str, session: Session = Depends(get_session)):
    svc = TaskService(session)
    ok = svc.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    session.commit()
    return {"status": "deleted", "id": task_id}
