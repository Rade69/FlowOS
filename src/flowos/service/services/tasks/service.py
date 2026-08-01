"""Task Service — CRUD za zadatke."""

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import Task


class TaskService:
    """Poslovna logika za upravljanje zadacima."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_tasks(self, project_id: str) -> list[Task]:
        return (
            self._session.query(Task)
            .filter(Task.project_id == project_id)
            .order_by(Task.created_at.desc())
            .all()
        )

    def get_task(self, task_id: str) -> Task | None:
        return self._session.get(Task, task_id)

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str | None = None,
        priority: str = "NORMAL",
        plan_item_id: str | None = None,
    ) -> Task:
        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            plan_item_id=plan_item_id,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        plan_item_id: str | None = None,
    ) -> Task | None:
        task = self._session.get(Task, task_id)
        if not task:
            return None
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if plan_item_id is not None:
            task.plan_item_id = plan_item_id
        # Ako je status DONE, postavi done_at
        from datetime import UTC, datetime

        if status == "DONE":
            task.done_at = datetime.now(tz=UTC)
        self._session.flush()
        return task

    def delete_task(self, task_id: str) -> bool:
        task = self._session.get(Task, task_id)
        if not task:
            return False
        self._session.delete(task)
        self._session.flush()
        return True
