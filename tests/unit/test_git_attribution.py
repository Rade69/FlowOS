"""Testovi za GitPoller i AttributionService."""

import tempfile
from pathlib import Path

from flowos.service.services.attribution.service import (
    ActiveSession,
    AttributionService,
)
from flowos.service.services.infrastructure.git_poller import GitPoller


class TestGitPoller:
    def test_poll_on_temp_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # Inicijalizuj git repo
            import subprocess

            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
            (repo / "test.txt").write_text("hello")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)

            poller = GitPoller(str(repo))
            state = poller.poll()

            assert state.commit_sha is not None
            assert state.branch is not None
            assert not state.is_dirty

    def test_dirty_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            import subprocess

            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
            (repo / "test.txt").write_text("hello")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)

            # Napravi dirty state
            (repo / "test.txt").write_text("modified")

            poller = GitPoller(str(repo))
            state = poller.poll()
            assert state.is_dirty
            assert "test.txt" in state.changed_files

    def test_detect_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            import subprocess

            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            poller = GitPoller(str(repo))
            s1 = poller.poll()

            (repo / "f.txt").write_text("v2")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c2"], cwd=str(repo), capture_output=True)

            s2 = poller.poll()
            changes = poller.detect_changes(s2)
            # detect_changes poredi sa _last_state — treba da detektuje promenu
            # Prvo ručno vratimo _last_state na s1
            poller._last_state = s1
            changes = poller.detect_changes(s2)
            assert changes["new_commits"]


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

    def test_sole_active(self):
        sessions = [ActiveSession(session_id="s1", repo_path="C:/repo")]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "SOLE_ACTIVE"
        assert result.confidence == "MEDIUM"

    def test_multiple_sessions_unattributed(self):
        sessions = [
            ActiveSession(session_id="s1", repo_path="C:/repo"),
            ActiveSession(session_id="s2", repo_path="C:/repo"),
        ]
        result = AttributionService.attribute("C:/repo/src/test.py", sessions)
        assert result.attribution == "UNATTRIBUTED"
        assert result.confidence == "LOW"