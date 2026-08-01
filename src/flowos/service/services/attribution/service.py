"""Attribution Service — atribucija promena fajlova sesijama.

Pravila:
- WORKTREE: fajl u worktree-ju sesije → pouzdana atribucija
- SOLE_ACTIVE: samo jedna aktivna sesija u tree-ju → vjerovatna
- HINT: hint match sa više aktivnih sesija → srednja pouzdanost
- UNATTRIBUTED: više sesija bez dokaza → niska pouzdanost
- USER: nijedna aktivna sesija → korisnik
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ActiveSession:
    session_id: str
    worktree_path: str | None = None
    repo_path: str = ""
    plan_item_id: str | None = None


@dataclass
class AttributionResult:
    file_path: str
    attribution: str  # WORKTREE, SOLE_ACTIVE, HINT, UNATTRIBUTED, USER
    session_id: str | None = None
    confidence: str = "LOW"  # HIGH, MEDIUM, LOW


class AttributionService:
    """Određuje kojoj sesiji pripada promena fajla."""

    @staticmethod
    def attribute(
        file_path: str,
        active_sessions: list[ActiveSession],
    ) -> AttributionResult:
        """Atribuira promenu fajla na osnovu aktivnih sesija."""
        if not active_sessions:
            return AttributionResult(file_path=file_path, attribution="USER")

        # WORKTREE — pouzdana atribucija
        for s in active_sessions:
            if s.worktree_path and _is_in_worktree(file_path, s.worktree_path):
                return AttributionResult(file_path=file_path, attribution="WORKTREE", session_id=s.session_id, confidence="HIGH")

        # SOLE_ACTIVE — samo jedna sesija
        if len(active_sessions) == 1:
            s = active_sessions[0]
            return AttributionResult(file_path=file_path, attribution="SOLE_ACTIVE", session_id=s.session_id, confidence="MEDIUM")

        # UNATTRIBUTED — više sesija
        return AttributionResult(file_path=file_path, attribution="UNATTRIBUTED", confidence="LOW")

    @staticmethod
    def attribute_batch(
        file_paths: list[str],
        active_sessions: list[ActiveSession],
    ) -> list[AttributionResult]:
        return [AttributionService.attribute(fp, active_sessions) for fp in file_paths]


def _is_in_worktree(file_path: str, worktree_path: str) -> bool:
    """Proverava da li je fajl unutar worktree putanje."""
    try:
        fp = Path(file_path).resolve()
        wt = Path(worktree_path).resolve()
        return str(fp).startswith(str(wt))
    except Exception:
        return False