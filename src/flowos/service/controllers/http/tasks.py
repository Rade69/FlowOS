"""HTTP API Controllers — Zadaci (CRUD).

Tanke rute sa Pydantic request/response modelima.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from flowos.service.services.tasks.service import TaskService
from flowos.shared.contracts.tasks import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


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


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(  # type: ignore[call-arg]
        id=t.id,
        project_id=t.project_id,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        plan_item_id=getattr(t, "plan_item_id", None),
        created_at=t.created_at,
        updated_at=t.updated_at,
        done_at=t.done_at,
    )


@router.get("", response_model=list[TaskResponse])
def list_tasks(project_id: str, session: Session = Depends(get_session)):
    return [_task_to_response(t) for t in TaskService(session).list_tasks(project_id)]


@router.post("", response_model=TaskResponse)
def create_task(data: TaskCreate, session: Session = Depends(get_session)):
    svc = TaskService(session)
    t = svc.create_task(
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
    )
    session.commit()
    return _task_to_response(t)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, session: Session = Depends(get_session)):
    t = TaskService(session).get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    return _task_to_response(t)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, data: TaskUpdate, session: Session = Depends(get_session)):
    t = TaskService(session).update_task(
        task_id,
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        plan_item_id=None,
    )
    if not t:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    session.commit()
    return _task_to_response(t)


@router.delete("/{task_id}")
def delete_task(task_id: str, session: Session = Depends(get_session)):
    ok = TaskService(session).delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Zadatak nije pronađen")
    session.commit()
    return {"status": "deleted", "id": task_id}
