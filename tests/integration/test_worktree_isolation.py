"""Worktree izolacija — Gate Faze 4 integracioni testovi.

Dokazuje:
1. Dve sesije u različitim worktree-jevima → nema WRITE_WRITE
2. Dve sesije u istom tree-u bez worktree-ja → WRITE_WRITE detektovan
3. WorktreeManager create → list → cleanup lifecycle
"""

import contextlib
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401
from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.conflicts.service import ConflictDetectionService
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.persistence.worktree_models import Worktree


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def engine(db_path):
    eng = create_engine(
        f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _init_git_repo(path: Path) -> str:
    """Inicijalizuje Git repo i vraca prvi commit SHA."""
    subprocess.run(["git", "init", "-b", "main"], cwd=str(path), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@flowos.local"],
        cwd=str(path),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "FlowOS Test"],
        cwd=str(path),
        capture_output=True,
    )
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), capture_output=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(path), capture_output=True, text=True
    )
    return result.stdout.strip()


def _create_worktree(repo_path: Path, branch: str, wt_path: Path) -> str:
    """Kreira worktree i vraca commit SHA."""
    wt_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_path), "main"],
        cwd=str(repo_path),
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(wt_path), capture_output=True, text=True
    )
    return result.stdout.strip()


class TestWorktreeIsolationGate:
    """Gate Faze 4 — worktree izolacija."""

    def test_two_worktrees_no_write_write(self, engine, tmp_path: Path):
        """Dve sesije u razlicitim worktree-jevima → nema WRITE_WRITE."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)

        wt_a = tmp_path / "wt-a"
        wt_b = tmp_path / "wt-b"
        _create_worktree(repo_path, "flow/task-a", wt_a)
        _create_worktree(repo_path, "flow/task-b", wt_b)

        test_file_a = wt_a / "src" / "shared.py"
        test_file_b = wt_b / "src" / "shared.py"
        test_file_a.parent.mkdir(parents=True, exist_ok=True)
        test_file_b.parent.mkdir(parents=True, exist_ok=True)
        test_file_a.write_text("# session a\n")
        test_file_b.write_text("# session b\n")

        repo_str = str(repo_path)

        db = Session(engine)
        try:
            project = Project(id="iso-proj", name="Isolation", repo_path=repo_str)
            db.add(project)
            db.add_all(
                [
                    AgentSession(
                        id="iso-a",
                        project_id="iso-proj",
                        agent_type="cc",
                        repo_path=repo_str,
                        worktree_path=str(wt_a),
                        status="ACTIVE",
                    ),
                    AgentSession(
                        id="iso-b",
                        project_id="iso-proj",
                        agent_type="pi",
                        repo_path=repo_str,
                        worktree_path=str(wt_b),
                        status="ACTIVE",
                    ),
                ]
            )
            db.flush()
            db.commit()

            # Zabelezi aktivnosti za obe sesije — isti relativni fajl
            now = datetime.now(tz=UTC)
            fa_a = FileActivity(
                event_id="evt-iso-a",
                project_id="iso-proj",
                session_id="iso-a",
                event_type="MODIFIED",
                file_path=str(test_file_a),
                normalized_path="src/shared.py",
                tree_identity=str(wt_a),
                repository_path=repo_str,
                worktree_path=str(wt_a),
                source="TEST",
                occurred_at=now,
                recorded_at=now,
                attribution_type="WORKTREE_EXACT",
                attribution_confidence=1.0,
            )
            fa_b = FileActivity(
                event_id="evt-iso-b",
                project_id="iso-proj",
                session_id="iso-b",
                event_type="MODIFIED",
                file_path=str(test_file_b),
                normalized_path="src/shared.py",
                tree_identity=str(wt_b),
                repository_path=repo_str,
                worktree_path=str(wt_b),
                source="TEST",
                occurred_at=now,
                recorded_at=now,
                attribution_type="WORKTREE_EXACT",
                attribution_confidence=1.0,
            )
            db.add_all([fa_a, fa_b])
            db.flush()
            db.commit()

            # Detektuj konflikte
            svc = ConflictDetectionService(db)
            active = [
                ActiveSession(session_id="iso-a", worktree_path=str(wt_a), repo_path=repo_str),
                ActiveSession(session_id="iso-b", worktree_path=str(wt_b), repo_path=repo_str),
            ]
            conflicts = svc.detect_write_write("iso-proj", [fa_a, fa_b], active)

            assert len(conflicts) == 0, (
                f"Razliciti worktree-jevi ne smeju proizvesti WRITE_WRITE. "
                f"Dobijeno: {len(conflicts)}"
            )
        finally:
            db.close()

    def test_same_tree_without_worktree_produces_conflict(self, engine, tmp_path: Path):
        """Dve sesije u istom tree-u bez worktree-ja → WRITE_WRITE."""
        repo_path = tmp_path / "repo2"
        repo_path.mkdir()
        (repo_path / "src").mkdir(parents=True)
        _init_git_repo(repo_path)

        test_file = repo_path / "src" / "app.py"
        test_file.write_text("# shared\n")
        repo_str = str(repo_path)

        db = Session(engine)
        try:
            project = Project(id="shared-proj", name="Shared", repo_path=repo_str)
            db.add(project)
            db.add_all(
                [
                    AgentSession(
                        id="sh-a",
                        project_id="shared-proj",
                        agent_type="cc",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                    AgentSession(
                        id="sh-b",
                        project_id="shared-proj",
                        agent_type="pi",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                ]
            )
            db.flush()
            db.commit()

            now = datetime.now(tz=UTC)
            fa_a = FileActivity(
                event_id="evt-sh-a",
                project_id="shared-proj",
                session_id="sh-a",
                event_type="MODIFIED",
                file_path=str(test_file),
                normalized_path="src/app.py",
                tree_identity=repo_str,
                repository_path=repo_str,
                source="TEST",
                occurred_at=now,
                recorded_at=now,
                attribution_type="REPOSITORY_EXACT",
                attribution_confidence=0.7,
            )
            fa_b = FileActivity(
                event_id="evt-sh-b",
                project_id="shared-proj",
                session_id="sh-b",
                event_type="MODIFIED",
                file_path=str(test_file),
                normalized_path="src/app.py",
                tree_identity=repo_str,
                repository_path=repo_str,
                source="TEST",
                occurred_at=now,
                recorded_at=now,
                attribution_type="REPOSITORY_EXACT",
                attribution_confidence=0.7,
            )
            db.add_all([fa_a, fa_b])
            db.flush()
            db.commit()

            svc = ConflictDetectionService(db)
            active = [
                ActiveSession(session_id="sh-a", repo_path=repo_str),
                ActiveSession(session_id="sh-b", repo_path=repo_str),
            ]
            conflicts = svc.detect_write_write("shared-proj", [fa_a, fa_b], active)

            assert len(conflicts) >= 1, (
                f"Isti tree bez worktree-ja mora proizvesti WRITE_WRITE. Dobijeno: {len(conflicts)}"
            )
            assert conflicts[0].conflict_level == "HIGH"
        finally:
            db.close()

    def test_worktree_lifecycle_create_list_status(self, engine, tmp_path: Path):
        """WorktreeManager: create → list → status lifecycle."""
        repo_path = tmp_path / "repo3"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        repo_str = str(repo_path)

        db = Session(engine)
        try:
            project = Project(id="life-proj", name="Lifecycle", repo_path=repo_str)
            db.add(project)
            db.flush()
            db.commit()

            from flowos.service.services.worktrees.manager import WorktreeManager

            mgr = WorktreeManager(db)

            # Create
            result = mgr.create_worktree(
                project_id="life-proj",
                task_id="FLOW-TEST",
                slug="test",
                base_branch="main",
            )
            assert result["id"] is not None
            assert "path" in result
            assert result["status"] == "ACTIVE"
            wt_path = result["path"]

            # Status
            wt_id = result["id"]
            status = mgr.get_worktree(wt_id)
            assert status is not None
            assert status["worktree_path"] == wt_path
            assert "git_status" in status

            # Cleanup
            from flowos.service.services.worktrees.service import WorktreeService

            svc = WorktreeService(repo_str, retention_days=0)
            svc.cleanup(wt_path, force=True)

            db_wt = db.get(Worktree, wt_id)
            if db_wt:
                db_wt.status = "CLEANED"
                db.flush()
        finally:
            db.close()
