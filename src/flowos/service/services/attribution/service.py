"""Attribution Service — atribucija promena fajlova sesijama.

Pravila:
- WORKTREE: fajl u worktree-ju sesije → HIGH confidence
- SOLE_ACTIVE: samo jedna sesija, fajl unutar njenog repo-a → MEDIUM
- UNATTRIBUTED: više sesija bez dokaza → LOW
- USER: nijedna aktivna sesija → korisnik
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ActiveSession:
    session_id: str
    worktree_path: str | None = None
    repo_path: str = ""


@dataclass
class AttributionResult:
    file_path: str
    attribution: str  # WORKTREE, SOLE_ACTIVE, UNATTRIBUTED, USER
    session_id: str | None = None
    confidence: str = "LOW"


class AttributionService:
    """Određuje kojoj sesiji pripada promena fajla."""

    @staticmethod
    def attribute(file_path: str, active_sessions: list[ActiveSession]) -> AttributionResult:
        if not active_sessions:
            return AttributionResult(file_path=file_path, attribution="USER")

        # WORKTREE — sigurna path provjera
        for s in active_sessions:
            if s.worktree_path and _is_in_worktree(file_path, s.worktree_path):
                return AttributionResult(file_path=file_path, attribution="WORKTREE", session_id=s.session_id, confidence="HIGH")

        # SOLE_ACTIVE — samo jedna sesija i fajl unutar njenog repo-a
        if len(active_sessions) == 1:
            s = active_sessions[0]
            if s.repo_path and _is_in_repo(file_path, s.repo_path):
                return AttributionResult(file_path=file_path, attribution="SOLE_ACTIVE", session_id=s.session_id, confidence="MEDIUM")
            return AttributionResult(file_path=file_path, attribution="UNATTRIBUTED", confidence="LOW")

        # UNATTRIBUTED — više sesija
        return AttributionResult(file_path=file_path, attribution="UNATTRIBUTED", confidence="LOW")


def _is_in_worktree(file_path: str, worktree_path: str) -> bool:
    """Sigurna provjera pripadnosti putanje worktree-ju koristeći is_relative_to."""
    try:
        fp = Path(file_path).resolve(strict=False)
        wt = Path(worktree_path).resolve(strict=False)
        return fp.is_relative_to(wt)
    except (ValueError, OSError):
        return False


def _is_in_repo(file_path: str, repo_path: str) -> bool:
    """Sigurna provjera pripadnosti putanje repozitorijumu."""
    try:
        fp = Path(file_path).resolve(strict=False)
        rp = Path(repo_path).resolve(strict=False)
        return fp.is_relative_to(rp)
    except (ValueError, OSError):
        return False