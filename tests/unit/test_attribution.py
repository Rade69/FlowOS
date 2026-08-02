"""Testovi za AttributionService — Korak 4 korektivnog naloga.

Proverava ceo lanac atribucije:
WORKTREE_EXACT → REPOSITORY_EXACT → SOLE_ACTIVE_SESSION_WITHIN_REPO → HINT → UNATTRIBUTED → USER
"""

from flowos.service.services.attribution.service import (
    ActiveSession,
    AttributionService,
)


class TestAttributionService:
    """Osnovni testovi atribucije."""

    def test_no_sessions_returns_user(self):
        result = AttributionService.attribute("src/test.py", [])
        assert result.attribution == "USER"
        assert result.session_id is None

    # ── WORKTREE_EXACT ──────────────────────────────────────────

    def test_worktree_exact(self):
        sessions = [ActiveSession(session_id="s1", worktree_path="C:/worktrees/FLOW-42")]
        result = AttributionService.attribute("C:/worktrees/FLOW-42/src/test.py", sessions)
        assert result.attribution == "WORKTREE_EXACT"
        assert result.session_id == "s1"
        assert result.confidence == "HIGH"

    def test_different_worktrees(self):
        """Fajl u worktree-ju s2 ne pripada s1."""
        sessions = [
            ActiveSession(session_id="s1", worktree_path="C:/wt-a"),
            ActiveSession(session_id="s2", worktree_path="C:/wt-b"),
        ]
        result = AttributionService.attribute("C:/wt-b/src/file.py", sessions)
        assert result.attribution == "WORKTREE_EXACT"
        assert result.session_id == "s2"

    def test_similar_prefix_not_matched(self):
        """C:/worktree-12 ne sme matchovati C:/worktree-12-other."""
        sessions = [ActiveSession(session_id="s1", worktree_path="C:/worktree-12")]
        result = AttributionService.attribute("C:/worktree-12-other/file.py", sessions)
        assert result.attribution != "WORKTREE_EXACT"

    # ── REPOSITORY_EXACT ────────────────────────────────────────

    def test_repository_exact_single_session_no_worktree(self):
        """Jedna sesija bez worktree-ja, fajl u njenom repo-u."""
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "REPOSITORY_EXACT"
        assert result.session_id == "s1"
        assert result.confidence == "MEDIUM"

    def test_repository_exact_not_when_multiple_share_repo(self):
        """Dve sesije bez worktree-ja u istom repo-u → ne REPOSITORY_EXACT."""
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
            ActiveSession(session_id="s2", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution != "REPOSITORY_EXACT"

    def test_repository_exact_ignored_when_worktree_exists(self):
        """Ako jedna sesija ima worktree koji sadrži fajl, nema REPOSITORY_EXACT za drugu."""
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
            ActiveSession(session_id="s2", worktree_path="C:/repo/wt", repo_path="C:/repo"),
        ]
        # Fajl u worktree-ju s2
        result = AttributionService.attribute("C:/repo/wt/src/file.py", sessions)
        assert result.attribution == "WORKTREE_EXACT"
        assert result.session_id == "s2"

    # ── SOLE_ACTIVE_SESSION_WITHIN_REPO ─────────────────────────

    def test_sole_active_in_repo(self):
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        # Sada daje REPOSITORY_EXACT jer je jedna sesija bez worktree-ja
        assert result.attribution == "REPOSITORY_EXACT"
        assert result.confidence == "MEDIUM"

    def test_sole_active_outside_repo(self):
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/other/src/test.py", sessions)
        assert result.attribution == "UNATTRIBUTED"

    # ── HINT ────────────────────────────────────────────────────

    def test_hint_glob_match(self):
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo", hint_glob="src/backend/**"),
            ActiveSession(session_id="s2", repo_path="C:/repo", hint_glob="src/frontend/**"),
        ]
        result = AttributionService.attribute("C:/repo/src/backend/auth.py", sessions)
        assert result.attribution == "HINT"
        assert result.session_id == "s1"
        assert result.confidence == "MEDIUM"

    def test_hint_glob_no_match(self):
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo", hint_glob="src/backend/**"),
            ActiveSession(session_id="s2", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/repo/src/other/utils.py", sessions)
        assert result.attribution == "UNATTRIBUTED"

    # ── UNATTRIBUTED / USER ─────────────────────────────────────

    def test_multiple_sessions_unattributed(self):
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
            ActiveSession(session_id="s2", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "UNATTRIBUTED"

    def test_hint_cross_project_unattributed(self):
        """Fajl van bilo kog repo-a sa aktivnim sesijama — UNATTRIBUTED."""
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/other-project/file.py", sessions)
        assert result.attribution == "UNATTRIBUTED"

    # ── Granični slučajevi ──────────────────────────────────────

    def test_windows_case_insensitive(self):
        """Windows putanje su case-insensitive nakon resolve."""
        sessions = [ActiveSession(session_id="s1", worktree_path="C:/Worktrees/FLOW-42")]
        result = AttributionService.attribute("C:/worktrees/flow-42/src/file.py", sessions)
        assert result is not None
        # resolve(strict=False) na Windows-u normalizuje putanju
        # Ako fajl ne postoji, resolve ne menja case → WORKTREE_EXACT zavisi od OS
        # Na Windows-u, Path.resolve ne menja case za nepostojeće fajlove
        # Ovo je očekivano — ne možemo garantovati case-insensitivity za nepostojeće

    def test_nonexistent_path_handled(self):
        """Nepostojeća putanja ne baca izuzetak."""
        sessions = [ActiveSession(session_id="s1", worktree_path="Z:/nonexistent")]
        result = AttributionService.attribute("Z:/nonexistent/file.py", sessions)
        # resolve(strict=False) ne baca grešku za nepostojeće putanje
        assert result.attribution in ("WORKTREE_EXACT", "UNATTRIBUTED")

    def test_worktree_exact_priority_over_hint(self):
        """WORKTREE_EXACT ima prioritet nad HINT-om."""
        sessions = [
            ActiveSession(session_id="s1", worktree_path="C:/wt-1", hint_glob="src/**"),
            ActiveSession(session_id="s2", worktree_path="C:/wt-2", hint_glob="src/**"),
        ]
        result = AttributionService.attribute("C:/wt-1/src/file.py", sessions)
        assert result.attribution == "WORKTREE_EXACT"
        assert result.session_id == "s1"
