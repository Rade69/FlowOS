"""Worktree Manager — servisni sloj za worktree operacije sa bazom.

Povezuje WorktreeService (Git operacije) sa persistence slojem (SQLAlchemy).
Kontroler poziva ovaj servis, ne persistence modele direktno.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import Project
from flowos.service.services.infrastructure.persistence.worktree_models import Worktree
from flowos.service.services.worktrees.service import (
    WorktreeError,
    WorktreeService,
)

logger = logging.getLogger("flowos.worktree_manager")


class WorktreeManager:
    """Upravljanje worktree-jima — kombinuje Git i DB operacije."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _get_service(self, repo_path: str, retention_days: int = 7) -> WorktreeService:
        return WorktreeService(repo_path, retention_days=retention_days)

    def create_worktree(
        self,
        project_id: str,
        task_id: str,
        *,
        slug: str = "",
        base_branch: str = "",
        retention_days: int = 7,
    ) -> dict:
        """Kreira worktree i zapisuje metadata u bazu."""
        project = self._db.get(Project, project_id)
        if not project:
            raise WorktreeError(f"Projekat nije pronađen: {project_id}")

        svc = self._get_service(project.repo_path, retention_days)
        info = svc.create(task_id=task_id, slug=slug, base_branch=base_branch)

        wt = Worktree(
            project_id=project_id,
            task_id=task_id,
            worktree_path=info.path,
            branch_name=info.branch,
            base_branch=base_branch or "main",
            base_commit_sha=info.commit_sha,
            status="ACTIVE",
            retention_days=retention_days,
        )
        self._db.add(wt)
        self._db.flush()

        # Emituj WebSocket događaj
        try:
            from flowos.service.services.infrastructure.events import event_bus

            event_bus.emit_sync(
                "worktree.created",
                {
                    "worktree_id": wt.id,
                    "project_id": project_id,
                    "task_id": task_id,
                    "branch_name": info.branch,
                    "worktree_path": info.path,
                },
            )
        except Exception:
            pass

        # Regeneriši resume
        try:
            from flowos.service.services.project_resume import ProjectResumeService

            ProjectResumeService(self._db).regenerate(project_id)
        except Exception:
            pass

        return {
            "id": wt.id,
            "path": info.path,
            "branch": info.branch,
            "commit_sha": info.commit_sha,
            "task_id": task_id,
            "retention_days": retention_days,
            "status": "ACTIVE",
        }

    def list_worktrees(self, project_id: str, flowos_only: bool = True) -> list[dict]:
        """Lista worktree-ja sa podacima iz baze i Git-a."""
        project = self._db.get(Project, project_id)
        if not project:
            raise WorktreeError(f"Projekat nije pronađen: {project_id}")

        svc = self._get_service(project.repo_path)
        git_worktrees = svc.list_flowos_worktrees() if flowos_only else svc.list_worktrees()

        db_wts = {
            wt.worktree_path: wt
            for wt in self._db.query(Worktree).filter(Worktree.project_id == project_id).all()
        }

        result = []
        for info in git_worktrees:
            entry = {
                "path": info.path,
                "branch": info.branch,
                "commit_sha": info.commit_sha,
                "is_main": info.is_main,
                "git_status": info.status,
            }
            db_wt = db_wts.get(info.path)
            if db_wt:
                entry["id"] = db_wt.id
                entry["task_id"] = db_wt.task_id
                entry["session_id"] = db_wt.session_id
                entry["db_status"] = db_wt.status
                entry["retention_days"] = db_wt.retention_days
                entry["created_at"] = db_wt.created_at.isoformat() if db_wt.created_at else None
                entry["integrated_at"] = (
                    db_wt.integrated_at.isoformat() if db_wt.integrated_at else None
                )
            result.append(entry)
        return result

    def get_worktree(self, worktree_id: str) -> dict | None:
        """Status worktree-ja sa Git i DB podacima."""
        wt = self._db.get(Worktree, worktree_id)
        if not wt:
            return None

        svc = self._get_service(wt.worktree_path)
        try:
            git_status = svc.get_status(wt.worktree_path)
        except WorktreeError:
            git_status = {"error": "Git status nije dostupan"}

        base = {
            "id": wt.id,
            "project_id": wt.project_id,
            "task_id": wt.task_id,
            "session_id": wt.session_id,
            "worktree_path": wt.worktree_path,
            "branch_name": wt.branch_name,
            "base_branch": wt.base_branch,
            "status": wt.status,
            "retention_days": wt.retention_days,
            "created_at": wt.created_at.isoformat() if wt.created_at else None,
            "git_status": git_status,
        }
        return base

    def cleanup_worktree(self, worktree_id: str, *, force: bool = False) -> dict:
        """Uklanja worktree uz retention i bezbednosne provere."""
        wt = self._db.get(Worktree, worktree_id)
        if not wt:
            raise WorktreeError(f"Worktree nije pronađen: {worktree_id}")

        # Provera aktivne sesije
        if wt.session_id:
            from flowos.service.services.infrastructure.persistence.models import AgentSession

            session = self._db.get(AgentSession, wt.session_id)
            if session and session.status in ("ACTIVE", "IDLE"):
                raise WorktreeError(
                    f"Worktree ima aktivnu sesiju ({wt.session_id}). Prvo završite sesiju."
                )

        # Provera konflikata
        if wt.has_conflicts:
            raise WorktreeError("Worktree ima otvorene konflikte. Prvo ih razrešite.")

        # Provera dirty stanja
        svc = self._get_service(wt.worktree_path)
        status = svc.get_status(wt.worktree_path)
        if not status.get("clean", False) and not force:
            raise WorktreeError(
                "Worktree ima nekomitovane izmene. Koristite force=True za prinudno brisanje."
            )

        # Retention provera
        if not force:
            now = datetime.now(tz=UTC)
            if wt.created_at:
                age = (now - wt.created_at).days
                if age < wt.retention_days:
                    remaining = wt.retention_days - age
                    raise WorktreeError(
                        f"Retention period nije istekao. Preostalo: {remaining} dana."
                    )

        svc.cleanup(wt.worktree_path, force=force)
        wt.status = "CLEANED"
        wt.cleaned_at = datetime.now(tz=UTC)
        self._db.flush()

        return {"status": "cleaned", "worktree_id": worktree_id}

    def assign_session(self, worktree_id: str, session_id: str) -> dict | None:
        """Povezuje sesiju sa worktree-jem. Odbija ako je već zauzet."""
        wt = self._db.get(Worktree, worktree_id)
        if not wt:
            return None

        # Provera da li worktree već ima aktivnu sesiju
        if wt.session_id and wt.session_id != session_id:
            from flowos.service.services.infrastructure.persistence.models import AgentSession

            existing = self._db.get(AgentSession, wt.session_id)
            if existing and existing.status in ("ACTIVE", "IDLE"):
                raise WorktreeError(
                    f"Worktree je već zauzet sesijom {wt.session_id}. "
                    f"Jedan worktree = najviše jedna writer sesija."
                )

        wt.session_id = session_id
        wt.last_activity_at = datetime.now(tz=UTC)
        self._db.flush()

        return self.get_worktree(worktree_id)

    def prepare_integration(self, worktree_id: str, base_branch: str = "main") -> dict:
        """Priprema integraciju worktree-ja."""
        wt = self._db.get(Worktree, worktree_id)
        if not wt:
            raise WorktreeError(f"Worktree nije pronađen: {worktree_id}")

        svc = self._get_service(wt.worktree_path)
        prep = svc.prepare_integration(wt.worktree_path, base_branch)

        return {
            "worktree_id": worktree_id,
            "worktree_path": wt.worktree_path,
            "branch_name": wt.branch_name,
            "base_branch": base_branch,
            "has_conflicts": prep["has_conflicts"],
            "changed_files": prep["changed_files"],
            "changed_count": prep["changed_count"],
            "diff": prep["diff"],
        }

    def mark_integrated(self, worktree_id: str, result_commit_sha: str = "") -> dict | None:
        """Označava worktree kao integrisan."""
        wt = self._db.get(Worktree, worktree_id)
        if not wt:
            return None
        wt.status = "INTEGRATED"
        wt.integrated_at = datetime.now(tz=UTC)
        if result_commit_sha:
            wt.result_commit_sha = result_commit_sha
        self._db.flush()

        return self.get_worktree(worktree_id)
