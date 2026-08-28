"""Conflict Detection Service — detekcija i upravljanje konfliktima.

Pravila (iz plana §11.4 / §7.3):
1. WRITE_WRITE: Dve aktivne sesije upisuju isti fajl u istom treeju unutar 10 min → HIGH
2. LATE_OVERLAP: Sesija upisuje fajl koji je druga menjala u zadnjih 30 min → MEDIUM
3. BRANCH_CHANGE: Branch/HEAD promenjen ispod aktivne sesije → MEDIUM
4. STALE_SESSION: Sesija bez aktivnosti i bez živog procesa >30 min → INFO
5. NO_COMMIT: Završetak ima izmene bez commita → INFO

Koristi FileActivity ORM objekte (autoritativni izvor), ne dict-ove.
"""

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession

logger = logging.getLogger("flowos.conflicts")


class ConflictDetectionService:
    """Detektuje konflikte koristeći FileActivity ORM modele."""

    def __init__(
        self,
        session: Session,
        *,
        write_window_minutes: int = 10,
        overlap_window_minutes: int = 30,
        stale_minutes: int = 30,
    ) -> None:
        self._session = session
        self.write_window = timedelta(minutes=write_window_minutes)
        self.overlap_window = timedelta(minutes=overlap_window_minutes)
        self.stale_window = timedelta(minutes=stale_minutes)

    def on_file_activity(
        self, activity: FileActivity, active_sessions: list[ActiveSession]
    ) -> None:
        """Callback za ActivityService — pokreće WRITE_WRITE i LATE_OVERLAP detekciju."""
        if len(active_sessions) < 2:
            return
        recent = self._get_recent_activities(activity.project_id, minutes=30)
        self.detect_write_write(activity.project_id, recent, active_sessions)
        self.detect_late_overlap(activity.project_id, recent, active_sessions)

    def _get_recent_activities(self, project_id: str, minutes: int) -> list[FileActivity]:
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=minutes)
        return (
            self._session.query(FileActivity)
            .filter(FileActivity.project_id == project_id, FileActivity.occurred_at >= cutoff)
            .order_by(FileActivity.occurred_at.desc())
            .all()
        )

    # ── Pravilo 1: WRITE_WRITE ──────────────────────────────────

    def detect_write_write(
        self,
        project_id: str,
        activities: list[FileActivity],
        active_sessions: list[ActiveSession],
    ) -> list[Conflict]:
        """Dve aktivne sesije upisuju isti fajl u istom treeju unutar write_window."""
        conflicts: list[Conflict] = []
        now = datetime.now(tz=UTC)
        cutoff = now - self.write_window

        active_map = {s.session_id: s for s in active_sessions}
        by_tree_and_file: dict[tuple[str, str], list[FileActivity]] = {}

        for a in activities:
            if not a.session_id or a.session_id not in active_map:
                continue
            occurred = a.occurred_at
            if occurred is None:
                continue  # type: ignore[unreachable]
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=UTC)
            if occurred < cutoff:
                continue

            tree_id = a.tree_identity or a.repository_path
            key = (a.normalized_path or a.file_path, tree_id)
            by_tree_and_file.setdefault(key, []).append(a)

        seen_keys: set[str] = set()

        for (file_path, tree_id), acts in by_tree_and_file.items():
            session_ids = list({a.session_id for a in acts if a.session_id})
            if len(session_ids) < 2:
                continue

            # Proveri da li su u različitim worktree-ovima
            worktrees = set()
            for sid in session_ids:
                s_info = active_map.get(sid)
                if s_info and s_info.worktree_path:
                    worktrees.add(s_info.worktree_path)
            if len(worktrees) > 1:
                continue

            sorted_ids = sorted(session_ids)
            raw_key = f"{project_id}:{file_path}:{tree_id}:{':'.join(sorted_ids)}:WRITE_WRITE"
            conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()

            if conflict_key in seen_keys:
                continue
            seen_keys.add(conflict_key)

            existing = self._find_existing_conflict(
                project_id, file_path, "WRITE_WRITE", session_ids
            )
            if existing:
                existing.last_seen_at = datetime.now(tz=UTC)
                existing.occurrence_count += 1
                self._update_conflict_evidence(
                    existing,
                    {"activity_event_ids": [a.event_id for a in acts if a.event_id]},
                )
                continue

            conflict = Conflict(
                project_id=project_id,
                file_path=file_path,
                conflict_key=conflict_key,
                session_ids_json=json.dumps(sorted_ids),
                conflict_level="HIGH",
                conflict_type="WRITE_WRITE",
                description=f"Fajl {file_path} menjaju sesije {', '.join(sorted_ids)} u istom tree-u ({tree_id}) unutar {self.write_window.total_seconds() / 60:.0f} min.",
                evidence_json=json.dumps(
                    {
                        "session_ids": sorted_ids,
                        "tree_identity": tree_id,
                        "file_path": file_path,
                        "window_minutes": self.write_window.total_seconds() / 60,
                        "detected_at": now.isoformat(),
                        "conflict_key": conflict_key,
                        "activity_event_ids": [a.event_id for a in acts if a.event_id],
                    }
                ),
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
            )
            self._session.add(conflict)
            conflicts.append(conflict)

        if conflicts:
            self._session.flush()
            self._emit_conflicts(conflicts)
            self._rebuild_resume(project_id)
        return conflicts

    # ── Pravilo 2: LATE_OVERLAP ─────────────────────────────────

    def detect_late_overlap(
        self,
        project_id: str,
        activities: list[FileActivity],
        active_sessions: list[ActiveSession],
    ) -> list[Conflict]:
        """Sesija upisuje fajl koji je druga menjala u zadnjih overlap_window min."""
        conflicts: list[Conflict] = []
        now = datetime.now(tz=UTC)
        cutoff = now - self.overlap_window

        active_ids = {s.session_id for s in active_sessions}
        by_file: dict[str, list[FileActivity]] = {}

        for a in activities:
            if not a.session_id:
                continue
            occurred = a.occurred_at
            if occurred is None:
                continue  # type: ignore[unreachable]
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=UTC)
            if occurred >= cutoff:
                by_file.setdefault(a.normalized_path or a.file_path, []).append(a)

        for file_path, acts in by_file.items():
            session_ids = list({a.session_id for a in acts if a.session_id})
            if len(session_ids) < 2:
                continue

            finished = [sid for sid in session_ids if sid not in active_ids]
            if not finished:
                continue

            existing = self._find_existing_conflict(
                project_id, file_path, "LATE_OVERLAP", session_ids
            )
            if existing:
                existing.last_seen_at = datetime.now(tz=UTC)
                existing.occurrence_count += 1
                self._update_conflict_evidence(
                    existing,
                    {"activity_event_ids": [a.event_id for a in acts if a.event_id]},
                )
                continue

            raw_key = f"{project_id}:{file_path}:LATE_OVERLAP:{':'.join(sorted(session_ids))}"
            conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()
            conflict = Conflict(
                project_id=project_id,
                file_path=file_path,
                conflict_key=conflict_key,
                session_ids_json=json.dumps(sorted(session_ids)),
                conflict_level="MEDIUM",
                conflict_type="LATE_OVERLAP",
                description=f"Fajl {file_path} menjan od strane sesije {session_ids} unutar {self.overlap_window.total_seconds() / 60:.0f} min.",
                evidence_json=json.dumps(
                    {
                        "session_ids": session_ids,
                        "finished_sessions": finished,
                        "window_minutes": self.overlap_window.total_seconds() / 60,
                        "detected_at": now.isoformat(),
                        "conflict_key": conflict_key,
                        "activity_event_ids": [a.event_id for a in acts if a.event_id],
                    }
                ),
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
            )
            self._session.add(conflict)
            conflicts.append(conflict)

        if conflicts:
            self._session.flush()
            self._emit_conflicts(conflicts)
            self._rebuild_resume(project_id)
        return conflicts

    # ── Pravilo 3: BRANCH_CHANGE ─────────────────────────────────

    def detect_branch_change(
        self,
        project_id: str,
        session: AgentSession,
        previous_branch: str,
        current_branch: str,
    ) -> Conflict | None:
        """Branch/HEAD promenjen ispod aktivne sesije."""
        file_path = f"branch:{previous_branch}→{current_branch}"
        raw_key = f"{project_id}:{file_path}:BRANCH_CHANGE:{session.id}"
        conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()
        existing = self._find_existing_conflict(
            project_id, file_path, "BRANCH_CHANGE", [session.id]
        )
        if existing:
            existing.last_seen_at = datetime.now(tz=UTC)
            existing.occurrence_count += 1
            self._update_conflict_evidence(
                existing,
                {"branch": f"{previous_branch}→{current_branch}"},
            )
            return None

        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            conflict_key=conflict_key,
            session_ids_json=json.dumps([session.id]),
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description=f"Branch promenjen ispod aktivne sesije {session.id}: {previous_branch} → {current_branch}.",
            evidence_json=json.dumps(
                {
                    "session_id": session.id,
                    "previous_branch": previous_branch,
                    "current_branch": current_branch,
                }
            ),
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            occurrence_count=1,
        )
        self._session.add(conflict)
        self._session.flush()
        self._emit_conflicts([conflict])
        self._rebuild_resume(project_id)
        return conflict

    # ── Pravilo 4: STALE_SESSION ─────────────────────────────────

    def detect_stale_session(
        self,
        project_id: str,
        session: AgentSession,
    ) -> Conflict | None:
        """Sesija bez fs aktivnosti, bez heartbeata, bez živog procesa > stale_window min.

        Provera uključuje: last_activity_at, last_heartbeat_at, PID, status.
        """
        now = datetime.now(tz=UTC)

        # Proveri da li je sesija još uvek aktivna
        if session.status not in ("ACTIVE", "IDLE"):
            return None

        # Normalizuj heartbeat timestamp (može biti naive iz SQLite)
        heartbeat = session.last_heartbeat_at
        if heartbeat and heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)

        # Heartbeat je svež — sesija je živa
        if heartbeat and (now - heartbeat) <= self.stale_window:
            return None

        # Normalizuj last_activity timestamp
        last_activity = session.last_activity_at
        if last_activity and last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)

        # Poslednja fs aktivnost je sveža — sesija je aktivna
        if last_activity and (now - last_activity) <= self.stale_window:
            return None

        # Ako nema ni activity ni heartbeat podataka, preskoči
        if last_activity is None and session.last_heartbeat_at is None:
            return None

        # PID provera — proveri da li je proces još živ
        pid = session.pid
        if pid is not None:
            import ctypes as _ctypes

            if sys.platform == "win32":
                try:
                    kernel32 = _ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(0x0400, False, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return None  # Proces je živ — nije stale
                except Exception:
                    pass

        file_path = f"session:{session.id}"
        raw_key = f"{project_id}:{file_path}:STALE_SESSION:{session.id}"
        conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()
        existing = self._find_existing_conflict(
            project_id, file_path, "STALE_SESSION", [session.id]
        )
        if existing:
            existing.last_seen_at = datetime.now(tz=UTC)
            existing.occurrence_count += 1
            self._update_conflict_evidence(
                existing,
                {
                    "last_activity_at": last_activity.isoformat() if last_activity else None,
                    "last_heartbeat_at": session.last_heartbeat_at.isoformat()
                    if session.last_heartbeat_at
                    else None,
                    "pid": pid,
                },
            )
            return None

        idle_minutes = (now - last_activity).total_seconds() / 60 if last_activity else 0
        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            conflict_key=conflict_key,
            session_ids_json=json.dumps([session.id]),
            conflict_level="INFO",
            conflict_type="STALE_SESSION",
            description=f"Sesija {session.id} bez aktivnosti {idle_minutes:.0f} min — predloži ABANDONED.",
            evidence_json=json.dumps(
                {
                    "session_id": session.id,
                    "last_activity_at": last_activity.isoformat() if last_activity else None,
                    "last_heartbeat_at": session.last_heartbeat_at.isoformat()
                    if session.last_heartbeat_at
                    else None,
                    "idle_minutes": idle_minutes,
                    "pid": pid,
                    "session_status": session.status,
                }
            ),
            first_seen_at=now,
            last_seen_at=now,
            occurrence_count=1,
        )
        self._session.add(conflict)
        self._session.flush()
        self._emit_conflicts([conflict])
        self._rebuild_resume(project_id)
        return conflict

    # ── Pravilo 5: NO_COMMIT ─────────────────────────────────────

    def detect_no_commit(
        self,
        project_id: str,
        session: AgentSession,
        dirty_files: list[str],
    ) -> Conflict | None:
        """Sesija završena sa izmenama bez commita."""
        if not dirty_files:
            return None

        file_path = f"session:{session.id}"
        raw_key = f"{project_id}:{file_path}:NO_COMMIT:{session.id}"
        conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()
        existing = self._find_existing_conflict(project_id, file_path, "NO_COMMIT", [session.id])
        if existing:
            existing.last_seen_at = datetime.now(tz=UTC)
            existing.occurrence_count += 1
            self._update_conflict_evidence(
                existing,
                {"dirty_files": dirty_files[:50], "total_dirty": len(dirty_files)},
            )
            return None

        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            conflict_key=conflict_key,
            session_ids_json=json.dumps([session.id]),
            conflict_level="INFO",
            conflict_type="NO_COMMIT",
            description=f"Sesija {session.id} završena sa {len(dirty_files)} izmenjenih fajlova bez commita.",
            evidence_json=json.dumps(
                {
                    "session_id": session.id,
                    "base_commit": session.base_commit_sha,
                    "result_commit": session.result_commit_sha,
                    "dirty_files": dirty_files[:50],
                    "total_dirty": len(dirty_files),
                    "repo_path": session.repo_path,
                    "worktree_path": session.worktree_path,
                }
            ),
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            occurrence_count=1,
        )
        self._session.add(conflict)
        self._session.flush()
        self._emit_conflicts([conflict])
        self._rebuild_resume(project_id)
        return conflict

    # ── Pomoćne metode ───────────────────────────────────────────

    def _find_existing_conflict(
        self,
        project_id: str,
        file_path: str,
        conflict_type: str,
        session_ids: list[str],
    ) -> Conflict | None:
        """Pronalazi postojeći otvoreni konflikt po conflict_key ili kompozitnom ključu."""
        session_ids_json = json.dumps(sorted(session_ids))
        raw_key = f"{project_id}:{file_path}:{conflict_type}:{':'.join(sorted(session_ids))}"
        conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()

        # Primarno: conflict_key
        existing = (
            self._session.query(Conflict)
            .filter(Conflict.conflict_key == conflict_key, Conflict.status == "OPEN")
            .first()
        )
        if existing:
            return existing

        # Fallback: kompozitni upit (za konflikte kreirane pre uvođenja conflict_key)
        return (
            self._session.query(Conflict)
            .filter(
                Conflict.project_id == project_id,
                Conflict.file_path == file_path,
                Conflict.conflict_type == conflict_type,
                Conflict.session_ids_json == session_ids_json,
                Conflict.status == "OPEN",
            )
            .first()
        )

    def _update_conflict_evidence(self, conflict: Conflict, new_data: dict) -> None:
        """Ažurira evidence_json postojećeg konflikta novim podacima.

        Postojeći evidence se čuva, a novi podaci se dodaju u listu
        `additional_observations` unutar evidence JSON-a.
        """
        try:
            existing = json.loads(conflict.evidence_json or "{}")
        except (json.JSONDecodeError, TypeError):
            existing = {}

        observations: list = existing.get("additional_observations", [])
        observations.append(
            {
                "observed_at": datetime.now(tz=UTC).isoformat(),
                "data": new_data,
            }
        )
        existing["additional_observations"] = observations
        existing["last_updated_at"] = datetime.now(tz=UTC).isoformat()
        conflict.evidence_json = json.dumps(existing)

    def acknowledge(self, conflict_id: str) -> Conflict | None:
        conflict = self._session.get(Conflict, conflict_id)
        if not conflict or conflict.status != "OPEN":
            return None
        conflict.status = "ACKNOWLEDGED"
        conflict.acknowledged_at = datetime.now(tz=UTC)
        self._session.flush()
        return conflict

    def resolve(self, conflict_id: str) -> Conflict | None:
        conflict = self._session.get(Conflict, conflict_id)
        if not conflict or conflict.status not in ("OPEN", "ACKNOWLEDGED"):
            return None
        conflict.status = "RESOLVED"
        conflict.resolved_at = datetime.now(tz=UTC)
        self._session.flush()

        # Emituj WebSocket događaj
        try:
            from flowos.service.services.infrastructure.events import event_bus

            event_bus.emit_sync(
                "conflict.resolved",
                {
                    "conflict_id": conflict.id,
                    "project_id": conflict.project_id,
                    "conflict_type": conflict.conflict_type,
                    "file_path": conflict.file_path,
                },
            )
        except Exception:
            pass

        # Regeneriši resume
        try:
            from flowos.service.services.project_resume import ProjectResumeService

            ProjectResumeService(self._session).regenerate(conflict.project_id)
        except Exception:
            pass

        return conflict

    def list_open(self, project_id: str) -> list[Conflict]:
        return (
            self._session.query(Conflict)
            .filter(Conflict.project_id == project_id, Conflict.status == "OPEN")
            .order_by(Conflict.detected_at.desc())
            .all()
        )

    @staticmethod
    def _emit_conflicts(conflicts: list[Conflict]) -> None:
        try:
            from flowos.service.services.infrastructure.events import event_bus

            for c in conflicts:
                event_bus.emit_sync(
                    "conflict.created",
                    {
                        "conflict_id": c.id,
                        "project_id": c.project_id,
                        "conflict_type": c.conflict_type,
                        "conflict_level": c.conflict_level,
                        "file_path": c.file_path,
                    },
                )
        except Exception:
            pass

    def _rebuild_resume(self, project_id: str) -> None:
        """Regeneriše Project Resume nakon promene stanja konflikta."""
        try:
            from flowos.service.services.project_resume import ProjectResumeService

            ProjectResumeService(self._session).regenerate(project_id)
        except Exception:
            pass
