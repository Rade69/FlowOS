"""Project Service — CRUD za projekte.

Koristi SQLAlchemy Session za perzistenciju.
Ne sme se importovati iz View ili Controller slojeva.
"""

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import Project


class ProjectService:
    """Poslovna logika za upravljanje projektima."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_projects(self) -> list[Project]:
        return self._session.query(Project).order_by(Project.created_at.desc()).all()

    def get_project(self, project_id: str) -> Project | None:
        return self._session.get(Project, project_id)

    def create_project(self, name: str, repo_path: str, notes: str | None = None) -> Project:
        project = Project(name=name, repo_path=repo_path, notes=notes)
        self._session.add(project)
        self._session.flush()
        return project

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        repo_path: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> Project | None:
        project = self._session.get(Project, project_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if repo_path is not None:
            project.repo_path = repo_path
        if notes is not None:
            project.notes = notes
        if status is not None:
            project.status = status
        self._session.flush()
        return project

    def delete_project(self, project_id: str) -> bool:
        project = self._session.get(Project, project_id)
        if not project:
            return False
        self._session.delete(project)
        self._session.flush()
        return True
