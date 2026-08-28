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
from flowos.service.services.infrastructure.redaction import redact_text
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.verification.service import VerificationService
from flowos.service.services.workflow.ledger import WorkflowLedgerService

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
        *,
        exit_code: int | None = None,
        result_commit_sha: str | None = None,
    ) -> None:
        """Izvršava sve post-session korake.

        Args:
            session_id: ID sesije koja se završava.
            exit_code: Izlazni kod agentskog procesa.
            result_commit_sha: Završni commit SHA (ako je agent commit-ovao).
        """
        logger.info("SessionCompletion: pokrecem za %s", session_id)

        # 1. Učitaj sesiju iz baze (sa Task-om i PlanItem-om)
        session = self._db.get(AgentSession, session_id)
        if not session:
            logger.error("SessionCompletion: sesija %s ne postoji", session_id)
            return

        project_id = session.project_id
        if not project_id:
            logger.error("SessionCompletion: sesija %s nema project_id — prekidanje", session_id)
            return

        repo_path = session.worktree_path or session.repo_path
        task_title = None

        if session.task_id:
            from flowos.service.services.infrastructure.persistence.models import Task

            task = self._db.get(Task, session.task_id)
            if task:
                task_title = task.title
                logger.info("SessionCompletion: task=%s", task_title)

        if session.plan_item_id:
            plan_item = self._db.get(PlanItem, session.plan_item_id)
            if plan_item:
                logger.info("SessionCompletion: plan_item=%s", plan_item.title)

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
        git_verified = False
        dirty_files: list[str] = []
        try:
            reader = GitStateReader(repo_path)
            git_state = reader.read_state()
            git_verified = True
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
        SessionTaskBindingService(self._db).close_active_binding(session_id, ended_at=now)

        if result_commit_sha:
            session.result_commit_sha = result_commit_sha

        # 4. Verifikacija
        verify_result = None
        verify_path = Path(repo_path) / "scripts" / "verify.py"
        if verify_path.is_file():
            logger.info("SessionCompletion: pokrecem verify.py za %s", session_id)
            svc = VerificationService()
            verify_result = svc.run_verify(repo_path, session_id=session_id, project_id=project_id)
            logger.info(
                "SessionCompletion: verify.py zavrsen (exit=%d, success=%s)",
                verify_result.exit_code,
                verify_result.success,
            )

            # Emituj WebSocket događaj
            from flowos.service.services.infrastructure.events import event_bus

            event_bus.emit_sync(
                "verification.completed",
                {
                    "session_id": session_id,
                    "project_id": project_id,
                    "artifact_id": verify_result.artifact_id,
                    "exit_code": verify_result.exit_code,
                    "success": verify_result.success,
                    "duration_seconds": verify_result.duration_seconds,
                },
            )

            # Zabeleži VERIFY_RESULT kao SessionEvent za timeline
            import json as _json

            from flowos.service.services.infrastructure.persistence.models import SessionEvent

            verify_metadata = {
                "artifact_id": verify_result.artifact_id,
                "exit_code": verify_result.exit_code,
                "duration_seconds": verify_result.duration_seconds,
                "timed_out": verify_result.timed_out,
                "success": verify_result.success,
                "verify_path": verify_result.verify_path,
            }
            verify_event = SessionEvent(
                session_id=session_id,
                event_type="VERIFY_RESULT",
                summary=f"Verify.py: {'PASS' if verify_result.success else 'FAIL'} (exit={verify_result.exit_code})",
                source="VERIFICATION_SERVICE",
                payload_json=_json.dumps(verify_metadata),
            )
            self._db.add(verify_event)
            # Flush PRIJE otvaranja SAVEPOINT-a: bez ovoga bi autoflush unutar
            # append_test_result() izvršio INSERT za verify_event TEK nakon
            # što je SAVEPOINT već otvoren, pa bi ga eventualni rollback do
            # savepoint-a obrisao zajedno sa neuspjelim Ledger appendom.
            self._db.flush()

            # TEST_RESULT Ledger append — izolovan SAVEPOINT-om (nested
            # transakcija) da neuspjeh ovog koraka ne obori ostatak
            # SessionCompletion transakcije (session facts, VERIFY_RESULT
            # SessionEvent i kasniji koraci moraju ostati commitabilni).
            try:
                with self._db.begin_nested():
                    WorkflowLedgerService(self._db).append_test_result(
                        project_id=project_id,
                        session_id=session_id,
                        result=verify_result,
                    )
            except Exception:
                logger.exception(
                    "SessionCompletion: TEST_RESULT Ledger append nije uspeo za %s", session_id
                )

        # Izvedi status — uzima u obzir exit code, verify
        session.status = self._derive_status(exit_code, verify_result)
        self._db.flush()

        # 5. Draft izveštaja
        verification_summary = None
        if verify_result:
            verification_summary = (
                f"Verify.py: {'prošao' if verify_result.success else 'pao'} "
                f"(exit={verify_result.exit_code}, trajanje={verify_result.duration_seconds:.1f}s)\n"
                f"stdout: {redact_text(verify_result.stdout)[:500]}\n"
                f"stderr: {redact_text(verify_result.stderr)[:500]}"
            )

        report_svc = ReportService(self._db)
        git_note = ""
        git_verification_status = "OK" if git_verified else "NOT_VERIFIED"
        if not git_verified:
            git_note = " (Git stanje NIJE provjereno)"
        report = report_svc.create_draft(
            session_id=session_id,
            summary=f"Sesija završena. Exit code: {exit_code}.{git_note}",
            commit_shas=[result_commit_sha] if result_commit_sha else None,
            verification_summary=(
                f"Git verification: {git_verification_status}\n{verification_summary}"
                if verification_summary
                else f"Git verification: {git_verification_status}"
            ),
        )
        logger.info("SessionCompletion: draft izvestaja kreiran %s", report.id)

        # Emituj WebSocket događaj
        from flowos.service.services.infrastructure.events import event_bus

        event_bus.emit_sync(
            "report.created",
            {
                "session_id": session_id,
                "project_id": project_id,
                "report_id": report.id,
            },
        )

        # 6. NO_COMMIT detekcija — samo ako je Git stanje uspešno pročitano
        if git_verified and dirty_files and not result_commit_sha:
            conflict_svc = ConflictDetectionService(self._db)
            conflict = conflict_svc.detect_no_commit(
                project_id=project_id,
                session=session,
                dirty_files=[str(f) for f in dirty_files],
            )
            if conflict:
                logger.info(
                    "SessionCompletion: NO_COMMIT konflikt — %d izmenjenih fajlova bez commita",
                    len(dirty_files),
                )

        # 7. Resume regeneracija
        try:
            from flowos.service.services.project_resume import ProjectResumeService

            resume_svc = ProjectResumeService(self._db)
            resume_svc.regenerate(project_id)
            logger.info("SessionCompletion: resume regenerisan za %s", project_id)
        except Exception as e:
            logger.warning("SessionCompletion: resume regeneracija nije uspela: %s", e)

        self._db.commit()
        logger.info("SessionCompletion: zavrseno za %s", session_id)

        # 8. Emituj WebSocket događaje
        try:
            from flowos.service.services.infrastructure.events import event_bus

            event_bus.emit_sync(
                "session.completed",
                {
                    "session_id": session_id,
                    "project_id": project_id,
                    "status": session.status,
                    "exit_code": exit_code,
                    "verification_passed": verify_result.success if verify_result else None,
                },
            )
            event_bus.emit_sync(
                "project.resume.updated",
                {
                    "project_id": project_id,
                },
            )
        except Exception as e:
            logger.warning("SessionCompletion: WebSocket emit nije uspeo: %s", e)

    @staticmethod
    def _derive_status(exit_code: int | None, verify_result=None) -> str:
        """Izvedi status sesije iz exit code-a i verify rezultata.

        - exit_code 0 + verify OK → COMPLETED
        - exit_code 0 + verify FAIL → NEEDS_REVIEW
        - exit_code != 0 → FAILED
        - exit_code is None → NEEDS_REVIEW (nepoznato stanje)
        """
        if exit_code is None:
            return "NEEDS_REVIEW"
        if exit_code == 0:
            if verify_result is not None and not verify_result.success:
                return "NEEDS_REVIEW"
            return "COMPLETED"
        return "FAILED"


class SessionCompletionError(Exception):
    """Greška pri završetku sesije."""
