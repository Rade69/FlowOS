"""Testovi za AttributionService."""

from flowos.service.services.attribution.service import (
    ActiveSession,
    AttributionService,
)


class TestAttributionService:
    def test_no_sessions_returns_user(self):
        result = AttributionService.attribute("src/test.py", [])
        assert result.attribution == "USER"

    def test_worktree_attribution(self):
        sessions = [ActiveSession(session_id="s1", worktree_path="C:/worktrees/FLOW-42")]
        result = AttributionService.attribute("C:/worktrees/FLOW-42/src/test.py", sessions)
        assert result.attribution == "WORKTREE"
        assert result.session_id == "s1"
        assert result.confidence == "HIGH"

    def test_sole_active_in_repo(self):
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "SOLE_ACTIVE"
        assert result.confidence == "MEDIUM"

    def test_sole_active_outside_repo(self):
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/other/src/test.py", sessions)
        assert result.attribution == "UNATTRIBUTED"

    def test_similar_prefix_not_matched(self):
        sessions = [ActiveSession(session_id="s1", worktree_path="C:/worktree-12")]
        result = AttributionService.attribute("C:/worktree-12-other/file.py", sessions)
        assert result.attribution != "WORKTREE"

    def test_multiple_sessions_unattributed(self):
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
            ActiveSession(session_id="s2", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "UNATTRIBUTED"