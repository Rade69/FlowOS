"""Conflict Detection Service — detekcija i upravljanje konfliktima.

Pravila (iz plana §11.4 / §7.3):
1. WRITE_WRITE: Dve aktivne sesije upisuju isti fajl u istom treeju unutar 10 min → HIGH
2. LATE_OVERLAP: Sesija upisuje fajl koji je druga menjala u zadnjih 30 min → MEDIUM
3. BRANCH_CHANGE: Branch/HEAD promenjen ispod aktivne sesije → MEDIUM
4. STALE_SESSION: Sesija bez aktivnosti i bez živog procesa >30 min → INFO
5. NO_COMMIT: Završetak ima izmene bez commita → INFO

Konfigurabilni pragovi se čuvaju kao parametri servisa.
"""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.conflict_models import Conflict


class ConflictDetectionService:
    """Detektuje konflikte među aktivnim sesijama na osnovu
    filesystem/Git događaja i pravila iz plana.

    Ne zavisi od konkretnog adaptera — koristi samo
    strukturisane podatke (FileActivity, GitChangeSet, AgentSession).
    """

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

    # ── Pravilo 1: WRITE_WRITE ──────────────────────────────────

    def detect_write_write(
        self,
        project_id: str,
        activities: list[dict],
        active_sessions: list[dict],
    ) -> list[Conflict]:
        """Dve aktivne sesije upisuju isti fajl u istom treeju unutar write_window.

        WRITE_WRITE konflikt nastaje samo kada su ispunjeni svi uslovi:
        - isti project_id
        - isti normalized_path
        - isti tree_identity (isti worktree ili isti repo bez worktree-ja)
        - različite aktivne sesije
        - vremenski prozori se preklapaju

        Ako su sesije u različitim worktree-ovima → nema konflikta.

        activities: lista dict-ova sa {file_path, session_id, observed_at, repo_path}
        active_sessions: lista dict-ova sa {id, worktree_path, repo_path}
        """
        import hashlib

        conflicts: list[Conflict] = []
        now = datetime.now(tz=UTC)
        cutoff = now - self.write_window

        # Izgradi mapu sesija: id → {worktree_path, repo_path}
        active_map = {s["id"]: s for s in active_sessions}

        # Grupisanje po (normalized_path, tree_identity)
        # tree_identity = worktree_path ako sesija ima worktree, inače repo_path
        by_tree_and_file: dict[tuple[str, str], list[dict]] = {}
        for a in activities:
            observed = a.get("observed_at")
            if isinstance(observed, str):
                observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
            if isinstance(observed, datetime) and observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if not observed or observed < cutoff:
                continue

            sid = a.get("session_id")
            if not sid:
                continue

            s_info = active_map.get(sid)
            if not s_info:
                continue

            # Odredi tree_identity
            wt = s_info.get("worktree_path")
            tree_id = wt if wt else s_info.get("repo_path", "")

            key = (a["file_path"], tree_id)
            by_tree_and_file.setdefault(key, []).append(a)

        seen_keys: set[str] = set()

        for (file_path, tree_id), acts in by_tree_and_file.items():
            session_ids = list({a["session_id"] for a in acts})
            if len(session_ids) < 2:
                continue

            # Proveri da li su u različitim worktree-ovima
            worktrees = set()
            for sid in session_ids:
                s_info = active_map.get(sid)
                if s_info and s_info.get("worktree_path"):
                    worktrees.add(s_info["worktree_path"])

            # Ako sesije imaju različite worktree putanje → nisu u istom tree-u → nema konflikta
            if len(worktrees) > 1:
                continue

            # Stabilan conflict_key za deduplikaciju
            sorted_ids = sorted(session_ids)
            raw_key = f"{project_id}:{file_path}:{tree_id}:{':'.join(sorted_ids)}:WRITE_WRITE"
            conflict_key = hashlib.sha256(raw_key.encode()).hexdigest()

            if conflict_key in seen_keys:
                continue
            seen_keys.add(conflict_key)

            # Proveri da li konflikt već postoji (OPEN)
            existing = self._find_existing_conflict(
                project_id, file_path, "WRITE_WRITE", session_ids
            )
            if existing:
                continue

            conflict = Conflict(
                project_id=project_id,
                file_path=file_path,
                session_ids_json=json.dumps(sorted_ids),
                conflict_level="HIGH",
                conflict_type="WRITE_WRITE",
                description=(
                    f"Fajl {file_path} menjaju sesije {', '.join(sorted_ids)} "
                    f"u istom tree-u ({tree_id}) unutar "
                    f"{self.write_window.total_seconds() / 60:.0f} min."
                ),
                evidence_json=json.dumps(
                    {
                        "session_ids": sorted_ids,
                        "tree_identity": tree_id,
                        "file_path": file_path,
                        "window_minutes": self.write_window.total_seconds() / 60,
                        "detected_at": now.isoformat(),
                        "conflict_key": conflict_key,
                    }
                ),
            )
            self._session.add(conflict)
            conflicts.append(conflict)

        if conflicts:
            self._session.flush()
        return conflicts

    # ── Pravilo 2: LATE_OVERLAP ─────────────────────────────────

    def detect_late_overlap(
        self,
        project_id: str,
        activities: list[dict],
        active_sessions: list[dict],
    ) -> list[Conflict]:
        """Sesija upisuje fajl koji je druga menjala u zadnjih overlap_window min."""
        conflicts: list[Conflict] = []
        now = datetime.now(tz=UTC)
        cutoff = now - self.overlap_window

        active_ids = {s["id"] for s in active_sessions}

        # Grupisanje po file_path
        by_file: dict[str, list[dict]] = {}
        for a in activities:
            observed = a.get("observed_at")
            if isinstance(observed, str):
                observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
            if isinstance(observed, datetime) and observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if observed and observed >= cutoff:
                by_file.setdefault(a["file_path"], []).append(a)

        for file_path, acts in by_file.items():
            session_ids = list({a["session_id"] for a in acts if a.get("session_id")})
            if len(session_ids) < 2:
                continue

            # Ako je jedan od njih već završio, to je overlap
            finished = [sid for sid in session_ids if sid not in active_ids]
            if not finished:
                continue

            existing = self._find_existing_conflict(
                project_id, file_path, "LATE_OVERLAP", session_ids
            )
            if existing:
                continue

            conflict = Conflict(
                project_id=project_id,
                file_path=file_path,
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
                    }
                ),
            )
            self._session.add(conflict)
            conflicts.append(conflict)

        if conflicts:
            self._session.flush()
        return conflicts

    # ── Pravilo 3: BRANCH_CHANGE ─────────────────────────────────

    def detect_branch_change(
        self,
        project_id: str,
        session: dict,
        previous_branch: str,
        current_branch: str,
    ) -> Conflict | None:
        """Branch/HEAD promenjen ispod aktivne sesije."""
        file_path = f"branch:{previous_branch}→{current_branch}"
        existing = self._find_existing_conflict(
            project_id, file_path, "BRANCH_CHANGE", [session["id"]]
        )
        if existing:
            return None

        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            session_ids_json=json.dumps([session["id"]]),
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description=f"Branch promenjen ispod aktivne sesije {session['id']}: {previous_branch} → {current_branch}.",
            evidence_json=json.dumps(
                {
                    "session_id": session["id"],
                    "previous_branch": previous_branch,
                    "current_branch": current_branch,
                }
            ),
        )
        self._session.add(conflict)
        self._session.flush()
        return conflict

    # ── Pravilo 4: STALE_SESSION ─────────────────────────────────

    def detect_stale_session(
        self,
        project_id: str,
        session: dict,
    ) -> Conflict | None:
        """Sesija bez fs aktivnosti i bez živog procesa > stale_window min."""
        last_activity = session.get("last_activity_at")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))

        now = datetime.now(tz=UTC)
        if last_activity is None or (now - last_activity) <= self.stale_window:
            return None

        file_path = f"session:{session['id']}"
        existing = self._find_existing_conflict(
            project_id, file_path, "STALE_SESSION", [session["id"]]
        )
        if existing:
            return None

        idle_minutes = (now - last_activity).total_seconds() / 60
        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            session_ids_json=json.dumps([session["id"]]),
            conflict_level="INFO",
            conflict_type="STALE_SESSION",
            description=f"Sesija {session['id']} bez aktivnosti {idle_minutes:.0f} min — predloži ABANDONED.",
            evidence_json=json.dumps(
                {
                    "session_id": session["id"],
                    "last_activity_at": last_activity.isoformat(),
                    "idle_minutes": idle_minutes,
                }
            ),
        )
        self._session.add(conflict)
        self._session.flush()
        return conflict

    # ── Pravilo 5: NO_COMMIT ─────────────────────────────────────

    def detect_no_commit(
        self,
        project_id: str,
        session: dict,
        dirty_files: list[str],
    ) -> Conflict | None:
        """Sesija završena sa izmenama bez commita."""
        if not dirty_files:
            return None

        file_path = f"session:{session['id']}"
        existing = self._find_existing_conflict(project_id, file_path, "NO_COMMIT", [session["id"]])
        if existing:
            return None

        conflict = Conflict(
            project_id=project_id,
            file_path=file_path,
            session_ids_json=json.dumps([session["id"]]),
            conflict_level="INFO",
            conflict_type="NO_COMMIT",
            description=f"Sesija {session['id']} završena sa {len(dirty_files)} izmenjenih fajlova bez commita.",
            evidence_json=json.dumps(
                {
                    "session_id": session["id"],
                    "dirty_files": dirty_files[:50],  # max 50
                    "total_dirty": len(dirty_files),
                }
            ),
        )
        self._session.add(conflict)
        self._session.flush()
        return conflict

    # ── Pomoćne metode ───────────────────────────────────────────

    def _find_existing_conflict(
        self,
        project_id: str,
        file_path: str,
        conflict_type: str,
        session_ids: list[str],
    ) -> Conflict | None:
        """Pronalazi postojeći OPEN konflikt istog tipa za isti fajl i sesije."""
        session_ids_json = json.dumps(sorted(session_ids))
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

    def acknowledge(self, conflict_id: str) -> Conflict | None:
        """Označava konflikt kao ACKNOWLEDGED."""
        conflict = self._session.get(Conflict, conflict_id)
        if not conflict or conflict.status != "OPEN":
            return None
        conflict.status = "ACKNOWLEDGED"
        conflict.acknowledged_at = datetime.now(tz=UTC)
        self._session.flush()
        return conflict

    def resolve(self, conflict_id: str) -> Conflict | None:
        """Označava konflikt kao RESOLVED."""
        conflict = self._session.get(Conflict, conflict_id)
        if not conflict or conflict.status not in ("OPEN", "ACKNOWLEDGED"):
            return None
        conflict.status = "RESOLVED"
        conflict.resolved_at = datetime.now(tz=UTC)
        self._session.flush()
        return conflict

    def list_open(self, project_id: str) -> list[Conflict]:
        """Vraća sve otvorene (OPEN) konflikte za projekat."""
        return (
            self._session.query(Conflict)
            .filter(
                Conflict.project_id == project_id,
                Conflict.status == "OPEN",
            )
            .order_by(Conflict.detected_at.desc())
            .all()
        )

    def list_by_project(self, project_id: str, status: str | None = None) -> list[Conflict]:
        """Vraća konflikte za projekat, opciono filtrirane po statusu."""
        q = self._session.query(Conflict).filter(Conflict.project_id == project_id)
        if status:
            q = q.filter(Conflict.status == status)
        return q.order_by(Conflict.detected_at.desc()).all()
