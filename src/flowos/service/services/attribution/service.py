"""Attribution Service — atribucija promena fajlova sesijama.

Prioritet atribucije (iz plana §7.3):
1. WORKTREE_EXACT: fajl u worktree-ju sesije → HIGH confidence
2. REPOSITORY_EXACT: fajl u repo-u sesije (nije u worktree-ju) → MEDIUM
3. SOLE_ACTIVE_SESSION_WITHIN_REPO: samo jedna sesija, fajl u njenom repo-u → MEDIUM
4. UNATTRIBUTED: više sesija bez dokaza → LOW
5. USER: nijedna aktivna sesija → korisnik

HINT je opcioni mehanizam za dodatnu atribuciju kada postoji više sesija.
Koristi fnmatch glob za poklapanje putanje.
"""

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ActiveSession:
    session_id: str
    worktree_path: str | None = None
    repo_path: str = ""
    hint_glob: str | None = None


@dataclass
class AttributionResult:
    file_path: str
    attribution: str  # WORKTREE, SOLE_ACTIVE, HINT, UNATTRIBUTED, USER
    session_id: str | None = None
    confidence: str = "LOW"


class AttributionService:
    """Određuje kojoj sesiji pripada promena fajla."""

    @staticmethod
    def attribute(file_path: str, active_sessions: list[ActiveSession]) -> AttributionResult:
        if not active_sessions:
            return AttributionResult(file_path=file_path, attribution="USER")

        # 1. WORKTREE_EXACT — fajl unutar worktree-ja sesije (najjači dokaz)
        for s in active_sessions:
            if s.worktree_path and _is_in_worktree(file_path, s.worktree_path):
                return AttributionResult(
                    file_path=file_path,
                    attribution="WORKTREE_EXACT",
                    session_id=s.session_id,
                    confidence="HIGH",
                )

        # 2. REPOSITORY_EXACT — fajl unutar repo-a sesije (bez worktree-ja)
        # Samo ako nijedna druga sesija ne deli isti repo niti ima worktree koji sadrži fajl
        repo_sessions: list[ActiveSession] = []
        for s in active_sessions:
            if s.repo_path and _is_in_repo(file_path, s.repo_path) and not s.worktree_path:
                repo_sessions.append(s)

        if len(repo_sessions) == 1:
            s = repo_sessions[0]
            # Proveri da neka druga sesija nema worktree koji sadrži ovaj fajl
            worktree_overlap = any(
                other.worktree_path
                and other.session_id != s.session_id
                and _is_in_worktree(file_path, other.worktree_path)
                for other in active_sessions
            )
            if not worktree_overlap:
                return AttributionResult(
                    file_path=file_path,
                    attribution="REPOSITORY_EXACT",
                    session_id=s.session_id,
                    confidence="MEDIUM",
                )

        # 3. SOLE_ACTIVE_SESSION_WITHIN_REPO — samo jedna sesija i fajl unutar njenog repo-a
        if len(active_sessions) == 1:
            s = active_sessions[0]
            if s.repo_path and _is_in_repo(file_path, s.repo_path):
                return AttributionResult(
                    file_path=file_path,
                    attribution="SOLE_ACTIVE_SESSION_WITHIN_REPO",
                    session_id=s.session_id,
                    confidence="MEDIUM",
                )
            return AttributionResult(
                file_path=file_path, attribution="UNATTRIBUTED", confidence="LOW"
            )

        # 4. HINT — više sesija, probaj hint_glob poklapanje
        for s in active_sessions:
            if s.hint_glob and _matches_hint(file_path, s.hint_glob, s.repo_path):
                return AttributionResult(
                    file_path=file_path,
                    attribution="HINT",
                    session_id=s.session_id,
                    confidence="MEDIUM",
                )

        # 5. UNATTRIBUTED — više sesija bez dokaza
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


def _matches_hint(file_path: str, hint_glob: str, repo_path: str) -> bool:
    """Proverava da li se putanja fajla poklapa sa hint glob-om.

    hint_glob može biti:
    - relativna putanja unutar repo-a: "src/flowos/**"
    - apsolutna putanja: "C:/repo/src/**"
    """
    fp = Path(file_path).resolve(strict=False)

    # Ako je hint apsolutan
    if os.path.isabs(hint_glob):
        try:
            hp = Path(hint_glob).resolve(strict=False)
            if fp.is_relative_to(hp.parent if hp.name else hp):
                # Jednostavno fnmatch na punoj putanji kao fallback
                return fnmatch.fnmatch(str(fp), hint_glob)
        except (ValueError, OSError):
            pass
        return fnmatch.fnmatch(str(fp), hint_glob)

    # Relativni hint — relativno u odnosu na repo_path
    if repo_path:
        try:
            base = Path(repo_path).resolve(strict=False)
            relative = fp.relative_to(base)
            return fnmatch.fnmatch(str(relative), hint_glob)
        except (ValueError, OSError):
            pass

    return False
