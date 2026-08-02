"""Session Completion Service — orkestracija završetka sesije.

Odgovornosti:
1. Učitava AgentSession, Project, Task, PlanItem iz baze
2. Očitava Git stanje (commit, branch, dirty, changed, untracked)
3. Pokreće verify.py (ako postoji)
4. Detektuje NO_COMMIT na osnovu stvarnih Git podataka
5. Kreira draft AgentReport
6. Ažurira status sesije

Koristi se iz session end endpoint-a kao background task.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from flowos.service.services.conflicts.service import ConflictDetectionService
from flowos.service.services.infrastructure.git_poller import GitStateReader
from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.service.services.infrastructure.persistence.plan_models import PlanItem
from flowos.service.services.reports.service import ReportService
from flowos.service.services.verification.service import VerificationService

logger = logging.getLogger("flowos.session_completion")


class SessionCompletionService:
    """Orkestrira sve korake pri završetku sesije.

    Učitava kompletan kontekst: sesiju, task, plan item, git stanje.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def complete_session(
        self,
        session_id: str,
        repo_path: str,
        *,
        exit_code: int | None = None,
        result_commit_sha: str | None = None,
    ) -> None:
        """Izvršava sve post-session korake.

        Args:
            session_id: ID sesije koja se završava.
            repo_path: Putanja do repozitorijuma.
            exit_code: Izlazni kod agentskog procesa.
            result_commit_sha: Završni commit SHA (ako je agent commit-ovao).
        """
        logger.info("SessionCompletion: pokrecem za %s", session_id)

        # 1. Učitaj sesiju iz baze (sa Task-om i PlanItem-om)
        session = self._db.get(AgentSession, session_id)
        if not session:
            logger.error("SessionCompletion: sesija %s ne postoji", session_id)
            return

        project_id = session.project_id or ""
        task_title = None
        plan_item_name = None

        if session.task_id:
            from flowos.service.services.infrastructure.persistence.models import Task

            task = self._db.get(Task, session.task_id)
            if task:
                task_title = task.title
                logger.info("SessionCompletion: task=%s", task_title)

        if session.plan_item_id:
            plan_item = self._db.get(PlanItem, session.plan_item_id)
            if plan_item:
                plan_item_name = plan_item.title
                logger.info("SessionCompletion: plan_item=%s", plan_item_name)

        logger.info(
            "SessionCompletion: sesija=%s agent=%s repo=%s worktree=%s branch=%s",
            session_id,
            session.agent_type,
            session.repo_path,
            session.worktree_path or "none",
            session.branch_name or "none",
        )

        # 2. Očitaj Git stanje
        git_state = None
        dirty_files: list[str] = []
        try:
            reader = GitStateReader(repo_path)
            git_state = reader._read_state()
            dirty_files = git_state.changed_files + git_state.untracked_files
            logger.info(
                "SessionCompletion: Git stanje — commit=%s, branch=%s, dirty=%s, promena=%d",
                git_state.commit_sha,
                git_state.branch,
                git_state.is_dirty,
                len(dirty_files),
            )
        except Exception:
            logger.exception("SessionCompletion: Git čitanje nije uspelo za %s", repo_path)

        # 3. Ažuriraj sesiju — zabeleži krajnje stanje
        now = datetime.now(tz=UTC)
        session.ended_at = now
        session.exit_code = exit_code

        # Izvedi status iz exit code-a, verify rezultata i timeout/cancel signala
        session.status = self._derive_status(exit_code)

        if result_commit_sha:
            session.result_commit_sha = result_commit_sha

        self._db.flush()

        # 4. Verifikacija
        verify_result = None
        verify_path = Path(repo_path) / "scripts" / "verify.py"
        if verify_path.is_file():
            logger.info("SessionCompletion: pokrecem verify.py za %s", session_id)
            svc = VerificationService()
            verify_result = svc.run_verify(repo_path)
            logger.info(
                "SessionCompletion: verify.py zavrsen (exit=%d, success=%s)",
                verify_result.exit_code,
                verify_result.success,
            )

        # 5. Draft izveštaja
        verification_summary = None
        if verify_result:
            verification_summary = (
                f"Verify.py: {'prošao' if verify_result.success else 'pao'} "
                f"(exit={verify_result.exit_code}, trajanje={verify_result.duration_seconds:.1f}s)\n"
                f"stdout: {verify_result.stdout[:500]}\n"
                f"stderr: {verify_result.stderr[:500]}"
            )

        report_svc = ReportService(self._db)
        report = report_svc.create_draft(
            session_id=session_id,
            summary=f"Sesija završena. Exit code: {exit_code}.",
            commit_shas=[result_commit_sha] if result_commit_sha else None,
            verification_summary=verification_summary,
        )
        logger.info("SessionCompletion: draft izvestaja kreiran %s", report.id)

        # 6. NO_COMMIT detekcija — koristi stvarne Git podatke
        if dirty_files and not result_commit_sha:
            conflict_svc = ConflictDetectionService(self._db)
            conflict = conflict_svc.detect_no_commit(
                project_id=project_id,
                session={"id": session_id},
                dirty_files=dirty_files,
            )
            if conflict:
                logger.info(
                    "SessionCompletion: NO_COMMIT konflikt — %d izmenjenih fajlova bez commita",
                    len(dirty_files),
                )

        self._db.commit()
        logger.info("SessionCompletion: zavrseno za %s", session_id)

    @staticmethod
    def _derive_status(exit_code: int | None) -> str:
        """Izvedi status sesije iz exit code-a.

        Pravila (iz centralne statusne mašine):
        - exit_code 0 → COMPLETED
        - exit_code != 0 → FAILED
        - exit_code is None → COMPLETED (nije dostupan, ali sesija je završena)
        """
        if exit_code is None:
            return "COMPLETED"
        if exit_code == 0:
            return "COMPLETED"
        return "FAILED"


class SessionCompletionError(Exception):
    """Greška pri završetku sesije."""
