"""Testovi za GitStateReader — stvarni privremeni Git repozitorijumi."""

import subprocess
import tempfile
from pathlib import Path

from flowos.service.services.infrastructure.git_poller import GitStateReader


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(path), capture_output=True)


class TestGitStateReader:
    def test_first_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            reader = GitStateReader(str(repo))
            state, changes = reader.poll_and_detect()
            assert state.commit_sha is not None
            assert changes.first_observation

    def test_no_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            reader = GitStateReader(str(repo))
            reader.poll_and_detect()
            _, changes = reader.poll_and_detect()
            assert not changes.commit_changed
            assert not changes.dirty_state_changed

    def test_new_commit_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            reader = GitStateReader(str(repo))
            reader.poll_and_detect()

            (repo / "f.txt").write_text("v2")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c2"], cwd=str(repo), capture_output=True)

            _, changes = reader.poll_and_detect()
            assert changes.commit_changed

    def test_dirty_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            reader = GitStateReader(str(repo))
            state, _ = reader.poll_and_detect()
            assert not state.is_dirty

            (repo / "f.txt").write_text("modified")
            state, changes = reader.poll_and_detect()
            assert state.is_dirty
            assert changes.dirty_state_changed

    def test_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            (repo / "new_file.py").write_text("untracked")

            reader = GitStateReader(str(repo))
            state, _ = reader.poll_and_detect()
            assert "new_file.py" in state.untracked_files

    def test_branch_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "f.txt").write_text("v1")
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=str(repo), capture_output=True)

            reader = GitStateReader(str(repo))
            s1, _ = reader.poll_and_detect()
            assert s1.branch is not None

            subprocess.run(["git", "checkout", "-b", "feature"], cwd=str(repo), capture_output=True)
            s2, changes = reader.poll_and_detect()
            assert changes.branch_changed

    def test_non_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = GitStateReader(tmp)
            state, changes = reader.poll_and_detect()
            assert state.commit_sha in (None, "")  # Nije git repo — nema greške, prazan SHA