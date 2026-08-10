"""Reconciliation Service — periodično Git poređenje i detekcija eksternih promena.

Tok:
1. GitStateReader.read_state()
2. Poređenje sa ProjectWorkspaceState
3. Klasifikacija razlike (HEAD_CHANGED, BRANCH_CHANGED, ...)
4. Ažuriranje workspace state-a
5. Kreiranje reconciliation event-a
6. Resume regeneracija
7. WebSocket emitovanje
"""

import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.git_poller import GitStateReader
from flowos.service.services.infrastructure.persistence.resume_models import (
    ProjectReconciliationEvent,
    ProjectWorkspaceState,
)

logger = logging.getLogger("flowos.reconciliation")

RECONCILIATION_CATEGORIES = [
    "HEAD_CHANGED",
    "BRANCH_CHANGED",
    "WORKTREE_DIRTY",
    "UNTRACKED_FILES",
    "FILES_CHANGED",
    "EXTERNAL_COMMIT",
    "FORCED_RESET",
    "REBASE_DETECTED",
    "UNKNOWN_CHANGE",
]


class ReconciliationService:
    """Upoređuje Git stanje sa poslednjim poznatim stanjem projekta."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def reconcile(self, project_id: str, repo_path: str) -> dict | None:
        """Izvršava jedan ciklus reconciliation-a za projekat.

        Returns:
            Rezultat sa kategorijama promena, ili None ako nema promena.
        """
        # 1. Čitaj Git stanje
        try:
            reader = GitStateReader(repo_path)
            git_state = reader.read_state()
        except Exception as e:
            logger.warning("Reconciliation: Git čitanje nije uspelo za %s: %s", repo_path, e)
            return None

        # 2. Nađi ili kreiraj workspace state
        ws_state = (
            self._db.query(ProjectWorkspaceState)
            .filter(ProjectWorkspaceState.project_id == project_id)
            .first()
        )
        if not ws_state:
            changed_files = git_state.changed_files + git_state.untracked_files
            ws_state = ProjectWorkspaceState(
                project_id=project_id,
                last_known_commit_sha=git_state.commit_sha,
                last_known_branch=git_state.branch,
                last_known_status_porcelain="\n".join(changed_files),
                last_known_dirty_fingerprint=_dirty_fingerprint(changed_files),
            )
            self._db.add(ws_state)
            ws_state.reconciliation_status = "CURRENT"
            self._db.flush()
            return None

        # 3. Klasifikuj razliku
        categories: list[str] = []
        changes_detected = False

        if (
            git_state.commit_sha
            and ws_state.last_known_commit_sha
            and git_state.commit_sha != ws_state.last_known_commit_sha
        ):
            categories.append("HEAD_CHANGED")
            categories.append("EXTERNAL_COMMIT")
            changes_detected = True

        if (
            git_state.branch
            and ws_state.last_known_branch
            and git_state.branch != ws_state.last_known_branch
        ):
            categories.append("BRANCH_CHANGED")
            changes_detected = True

        changed_files = git_state.changed_files + git_state.untracked_files
        dirty_fingerprint = _dirty_fingerprint(changed_files)
        previous_dirty = bool(ws_state.last_known_status_porcelain)
        if git_state.is_dirty != previous_dirty:
            categories.append("WORKTREE_DIRTY")
            changes_detected = True

        if changed_files:
            categories.append("FILES_CHANGED")
            changes_detected = True

        if not changes_detected:
            ws_state.reconciliation_status = "CURRENT"
            ws_state.last_reconciled_at = datetime.now(tz=UTC)
            self._db.flush()
            return None

        # 4. Ažuriraj workspace state
        previous_commit_sha = ws_state.last_known_commit_sha
        previous_branch = ws_state.last_known_branch
        previous_dirty_fingerprint = ws_state.last_known_dirty_fingerprint
        ws_state.last_known_commit_sha = git_state.commit_sha
        ws_state.last_known_branch = git_state.branch
        ws_state.last_known_status_porcelain = "\n".join(changed_files)
        ws_state.last_known_dirty_fingerprint = dirty_fingerprint
        ws_state.reconciliation_status = "EXTERNAL_CHANGES"
        ws_state.external_change_summary = ", ".join(categories)
        ws_state.last_reconciled_at = datetime.now(tz=UTC)

        # 5. Kreiraj reconciliation event
        event = ProjectReconciliationEvent(
            project_id=project_id,
            previous_commit_sha=previous_commit_sha,
            current_commit_sha=git_state.commit_sha,
            previous_branch=previous_branch,
            current_branch=git_state.branch,
            previous_dirty_fingerprint=previous_dirty_fingerprint,
            current_dirty_fingerprint=dirty_fingerprint,
            result="EXTERNAL_CHANGES",
            new_commit_shas_json=json.dumps([git_state.commit_sha] if git_state.commit_sha else []),
            changed_files_json=json.dumps(changed_files),
            occurred_at=datetime.now(tz=UTC),
        )
        self._db.add(event)

        # 6. Resume regeneracija
        try:
            from flowos.service.services.project_resume import ProjectResumeService

            resume_svc = ProjectResumeService(self._db)
            resume_svc.regenerate(project_id)
        except Exception as e:
            logger.warning("Reconciliation: resume regeneracija nije uspela: %s", e)

        self._db.flush()

        # 7. WebSocket
        try:
            from flowos.service.controllers.websocket.events import event_bus

            event_bus.emit_sync(
                "reconciliation.created",
                {
                    "project_id": project_id,
                    "categories": categories,
                    "commit": git_state.commit_sha,
                    "branch": git_state.branch,
                },
            )
        except Exception:
            pass

        logger.info(
            "Reconciliation: promene detektovane za %s: %s",
            project_id,
            ", ".join(categories),
        )

        return {
            "project_id": project_id,
            "categories": categories,
            "commit_sha": git_state.commit_sha,
            "branch": git_state.branch,
            "changed_files": len(changed_files),
            "dirty": git_state.is_dirty,
        }


def _dirty_fingerprint(changed_files: list[str]) -> str | None:
    if not changed_files:
        return None
    payload = "\n".join(sorted(changed_files)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
