"""Activity Service — beleženje filesystem događaja u bazu.

Koristi FileActivity ORM model za trajno čuvanje svakog watcher događaja.
Povezan je sa AttributionService za automatsku atribuciju.

Odgovornosti:
1. Primiti watcher događaj
2. Normalizovati putanju
3. Pozvati AttributionService
4. Kreirati i sačuvati FileActivity zapis
5. Vratiti strukturisan rezultat
6. Emitovati callback za conflict tok
"""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from flowos.service.services.attribution.service import (
    ActiveSession,
    AttributionResult,
    AttributionService,
)
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity

logger = logging.getLogger("flowos.activity")


class ActivityService:
    """Beleži filesystem aktivnost za potrebe atribucije i detekcije konflikata.

    Svaki događaj postaje trajni FileActivity zapis u bazi.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._conflict_callbacks: list[Callable[[FileActivity], None]] = []

    def register_conflict_callback(self, callback: Callable[[FileActivity], None]) -> None:
        """Registruje callback koji se poziva nakon svakog zabeleženog događaja.

        Koristi ga ConflictDetectionService za detekciju WRITE_WRITE i LATE_OVERLAP.
        """
        self._conflict_callbacks.append(callback)

    # ── Glavna metoda ──────────────────────────────────────────

    def record_file_event(
        self,
        *,
        file_path: str,
        event_type: str,
        project_id: str,
        repo_path: str,
        active_sessions: list[ActiveSession] | None = None,
        source: str = "WATCHER",
        metadata: dict | None = None,
    ) -> FileActivity:
        """Zapisuje filesystem događaj kao trajni FileActivity zapis.

        Args:
            file_path: Apsolutna ili relativna putanja do fajla.
            event_type: CREATED, MODIFIED, DELETED.
            project_id: ID projekta kome događaj pripada.
            repo_path: Putanja do repozitorijuma.
            active_sessions: Lista aktivnih sesija za atribuciju.
            source: Izvor događaja (WATCHER, GIT_POLL, MANUAL).
            metadata: Opcioni rečnik sa dodatnim kontekstom.

        Returns:
            Kreirani FileActivity ORM objekat.
        """
        import json

        # Normalizacija putanje
        normalized = _normalize_path(file_path)
        worktree_path = _extract_worktree_path(file_path, active_sessions or [])
        tree_identity = _derive_tree_identity(file_path, repo_path, active_sessions)

        # Atribucija
        attribution_type = "UNATTRIBUTED"
        attribution_confidence = 0.0
        session_id = None

        if active_sessions:
            result: AttributionResult = AttributionService.attribute(file_path, active_sessions)
            attribution_type = result.attribution
            attribution_confidence = _confidence_to_float(result.confidence)
            session_id = result.session_id

        occurred_at = datetime.now(tz=UTC)
        event_id = _generate_event_id(file_path, event_type, occurred_at)

        # Kreiranje ORM objekta
        activity = FileActivity(
            event_id=event_id,
            idempotency_key=None,  # event_id je dovoljan za dedup
            project_id=project_id,
            session_id=session_id,
            event_type=event_type,
            file_path=file_path,
            normalized_path=normalized,
            tree_identity=tree_identity,
            repository_path=repo_path,
            worktree_path=worktree_path,
            attribution_type=attribution_type,
            attribution_confidence=attribution_confidence,
            occurred_at=occurred_at,
            source=source,
            metadata_json=json.dumps(metadata) if metadata else None,
        )

        try:
            self._db.add(activity)
            self._db.flush()
            logger.debug(
                "FileActivity: %s %s attr=%s session=%s",
                event_type,
                file_path,
                attribution_type,
                session_id or "none",
            )
        except Exception:
            self._db.rollback()
            logger.exception("Greška pri zapisu FileActivity: %s %s", event_type, file_path)
            raise

        # Emitovanje conflict callback-ova
        for cb in self._conflict_callbacks:
            try:
                cb(activity)
            except Exception:
                logger.exception("Conflict callback greška za %s", event_id)

        return activity

    # ── Query metode ────────────────────────────────────────────

    def get_recent_activities(self, project_id: str, minutes: int = 30) -> list[FileActivity]:
        """Vraća nedavne aktivnosti za projekat unutar vremenskog prozora."""
        from datetime import timedelta

        cutoff = datetime.now(tz=UTC) - timedelta(minutes=minutes)
        return (
            self._db.query(FileActivity)
            .filter(
                FileActivity.project_id == project_id,
                FileActivity.occurred_at >= cutoff,
            )
            .order_by(FileActivity.occurred_at.desc())
            .all()
        )

    def get_session_activities(self, session_id: str) -> list[FileActivity]:
        """Vraća sve aktivnosti pripisane određenoj sesiji."""
        return (
            self._db.query(FileActivity)
            .filter(FileActivity.session_id == session_id)
            .order_by(FileActivity.occurred_at.desc())
            .all()
        )

    def get_file_activities(
        self, file_path: str, project_id: str | None = None
    ) -> list[FileActivity]:
        """Vraća sve aktivnosti za određeni fajl, opciono filtrirane po projektu."""
        normalized = _normalize_path(file_path)
        q = self._db.query(FileActivity).filter(FileActivity.normalized_path == normalized)
        if project_id:
            q = q.filter(FileActivity.project_id == project_id)
        return q.order_by(FileActivity.occurred_at.desc()).all()

    def get_project_activities(
        self,
        project_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[FileActivity]:
        """Vraća aktivnosti za projekat sa paginacijom."""
        return (
            self._db.query(FileActivity)
            .filter(FileActivity.project_id == project_id)
            .order_by(FileActivity.occurred_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


# ── Pomoćne funkcije ─────────────────────────────────────────


def _normalize_path(path: str) -> str:
    """Normalizuje putanju za poređenje.

    - resolve(strict=False) za apsolutnu putanju
    - lowercase na Windows-u
    - forward slash → backslash na Windows-u
    """
    try:
        p = Path(path).resolve(strict=False)
        normalized = str(p)
        # Windows case-insensitive
        if hasattr(p, "drive"):
            normalized = normalized.lower()
        return normalized
    except (ValueError, OSError):
        return path.lower() if hasattr(Path(path), "drive") else path


def _derive_tree_identity(
    file_path: str, repo_path: str, active_sessions: list[ActiveSession] | None = None
) -> str:
    """Izračunava tree_identity na osnovu putanje fajla i repo putanje.

    Ako je fajl unutar worktree-ja neke aktivne sesije,
    tree_identity je normalizovana worktree putanja.
    Inače je normalizovana repo putanja.
    """
    if active_sessions:
        wt = _extract_worktree_path(file_path, active_sessions)
        if wt:
            return _normalize_path(wt)
    return _normalize_path(repo_path)


def _extract_worktree_path(file_path: str, active_sessions: list[ActiveSession]) -> str | None:
    """Pokušava da izvuče worktree_path iz aktivnih sesija ako se fajl tamo nalazi."""
    for s in active_sessions:
        if s.worktree_path:
            try:
                fp = Path(file_path).resolve(strict=False)
                wt = Path(s.worktree_path).resolve(strict=False)
                if fp.is_relative_to(wt):
                    return str(wt)
            except (ValueError, OSError):
                continue
    return None


def _confidence_to_float(confidence: str) -> float:
    """Konvertuje string confidence u float."""
    mapping = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1}
    return mapping.get(confidence, 0.0)


def _generate_event_id(file_path: str, event_type: str, occurred_at: datetime) -> str:
    """Generiše jedinstveni event_id za deduplikaciju."""
    ts = occurred_at.strftime("%Y%m%d%H%M%S%f")
    uid = str(uuid.uuid4())[:8]
    return f"{event_type}-{ts}-{uid}"
