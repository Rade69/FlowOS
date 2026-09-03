"""Regression testovi za FLOW-1110 — siguran identitet worktree putanja.

Dokazuje da path identity ne koristi textual prefix, da managed root
membership koristi structural containment, i da `force=True` ne zaobilazi
hard identity/scope zaštite pri destructive cleanup odluci.
"""

import os
from pathlib import Path

import pytest

from flowos.service.services.worktrees.service import (
    WorktreeError,
    WorktreeInfo,
    WorktreeService,
)


def _service(tmp_path: Path, repo_name: str = "repo") -> WorktreeService:
    repo = tmp_path / repo_name
    repo.mkdir()
    return WorktreeService(str(repo))


def _info(path: str, *, is_main: bool = False) -> WorktreeInfo:
    return WorktreeInfo(
        path=path,
        branch="flow/test",
        commit_sha="abc123",
        is_main=is_main,
    )


# ── Exact identity ────────────────────────────────────────────


def test_exact_match(tmp_path: Path):
    """T1 — tačna canonical putanja mora biti MATCH."""
    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "FLOW-1"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]

    assert svc._find_worktree(str(wt_path)) is not None


def test_prefix_collision_no_match(tmp_path: Path):
    """T2 — FLOW-1 ne sme identifikovati FLOW-10."""
    svc = _service(tmp_path)
    wt_10 = svc.worktrees_dir / "FLOW-10"
    wt_10.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_10))]

    query = svc.worktrees_dir / "FLOW-1"
    assert svc._find_worktree(str(query)) is None


# ── Managed root membership ───────────────────────────────────


def test_managed_root_sibling_not_included(tmp_path: Path):
    """T3 — sibling `worktrees-old` nije unutar managed root `worktrees`."""
    svc = _service(tmp_path)
    sibling = svc._repo.parent / "worktrees-old" / "FLOW-1"
    sibling.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(sibling))]

    assert svc.list_flowos_worktrees() == []


def test_child_under_managed_root_included(tmp_path: Path):
    """T4 — `worktrees/FLOW-1` jeste managed."""
    svc = _service(tmp_path)
    child = svc.worktrees_dir / "FLOW-1"
    child.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(child))]

    assert len(svc.list_flowos_worktrees()) == 1


# ── Canonical form ────────────────────────────────────────────


def test_separator_form_no_false_mismatch(tmp_path: Path):
    """T5 — ekvivalentna reprezentacija iste putanje nije lažni mismatch."""
    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "FLOW-1"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]

    alt = str(wt_path) + os.sep
    assert svc._find_worktree(alt) is not None


def test_windows_case_semantics(tmp_path: Path):
    """T6 — na Windowsu case varijanta je isti path (platform-aware)."""
    if os.name != "nt":
        pytest.skip("Windows-only case semantics")

    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "FLOW-1"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]

    assert svc._find_worktree(str(wt_path).lower()) is not None


# ── Fail-closed cleanup ───────────────────────────────────────


def _spy_git(svc: WorktreeService):
    calls: list[list[str]] = []
    svc._git = lambda args, cwd=None: calls.append(args) or ""
    return calls


def test_unknown_cleanup_fails_closed(tmp_path: Path):
    """T7 — nepoznata putanja ne sme pokrenuti `git worktree remove`."""
    svc = _service(tmp_path)
    svc.list_worktrees = lambda: []
    calls = _spy_git(svc)

    with pytest.raises(WorktreeError):
        svc.cleanup(str(tmp_path / "ghost"), force=False)

    assert not any("remove" in a for a in calls)


def test_force_does_not_bypass_unknown(tmp_path: Path):
    """T8 — force ne zaobilazi unknown/unmanaged identitet."""
    svc = _service(tmp_path)
    svc.list_worktrees = lambda: []
    calls = _spy_git(svc)

    with pytest.raises(WorktreeError):
        svc.cleanup(str(tmp_path / "ghost"), force=True)

    assert not any("remove" in a for a in calls)


def test_force_does_not_bypass_main(tmp_path: Path):
    """T8 — force ne zaobilazi main worktree zaštitu."""
    svc = _service(tmp_path)
    svc.list_worktrees = lambda: [_info(str(svc._repo), is_main=True)]
    calls = _spy_git(svc)

    with pytest.raises(WorktreeError):
        svc.cleanup(str(svc._repo), force=True)

    assert not any("remove" in a for a in calls)


def test_exact_valid_cleanup(tmp_path: Path):
    """T9 — tačan valid managed worktree prolazi dozvoljeni cleanup tok."""
    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "FLOW-1"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]
    svc.get_status = lambda path: {"exists": True, "clean": True, "has_conflicts": False}
    calls = _spy_git(svc)

    svc.cleanup(str(wt_path), force=False)

    assert calls == [["worktree", "remove", str(wt_path)]]


def test_wrong_prefix_never_removes_other_tree(tmp_path: Path):
    """T10 — query FLOW-1 nikad ne sme obrisati FLOW-10."""
    svc = _service(tmp_path)
    wt_10 = svc.worktrees_dir / "FLOW-10"
    wt_10.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_10))]
    svc.get_status = lambda path: {"exists": True, "clean": True, "has_conflicts": False}
    calls = _spy_git(svc)

    query = svc.worktrees_dir / "FLOW-1"
    with pytest.raises(WorktreeError):
        svc.cleanup(str(query), force=True)

    assert not any("remove" in a for a in calls)
    assert not any("FLOW-10" in str(a) for a in calls)


# ── Project binding ───────────────────────────────────────────


def test_manager_cleanup_uses_project_repo_path(tmp_path: Path):
    """T11 — Manager vezuje WorktreeService za Project.repo_path, ne worktree path."""
    from flowos.service.services.worktrees.manager import WorktreeManager

    repo = tmp_path / "repo"
    repo.mkdir()
    wt_path = tmp_path / "worktrees" / "FLOW-1"
    wt_path.mkdir(parents=True)

    class FakeWorktree:
        id = "w1"
        project_id = "p1"
        session_id = None
        has_conflicts = False
        worktree_path = str(wt_path)
        retention_days = 0
        created_at = None
        status = "ACTIVE"

    class FakeProject:
        repo_path = str(repo)

    class FakeDb:
        def get(self, model, id_):
            if id_ == "w1":
                return FakeWorktree()
            if id_ == "p1":
                return FakeProject()
            return None

        def flush(self):
            pass

    captured: dict[str, str] = {}

    class FakeService:
        def __init__(self, repo_path, retention_days=7):
            captured["repo_path"] = repo_path

        def get_status(self, path):
            return {"exists": True, "clean": True, "has_conflicts": False}

        def cleanup(self, path, force=False):
            captured["cleanup_path"] = path

    mgr = WorktreeManager(FakeDb())
    mgr._get_service = lambda repo_path, retention_days=7: FakeService(repo_path, retention_days)

    result = mgr.cleanup_worktree("w1", force=True)

    assert result["status"] == "cleaned"
    assert captured["repo_path"] == str(repo)
    assert captured["cleanup_path"] == str(wt_path)


# ── FLOW-1110-CX-01 / CX-02 — matched path authority ──────────


def test_cleanup_remove_uses_registered_absolute_path(tmp_path: Path, monkeypatch):
    """CX-01 — relative CWD input: remove dobija registered apsolutni matched path."""
    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "RELATIVE"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]
    svc.get_status = lambda path: {"exists": True, "clean": True, "has_conflicts": False}
    calls = _spy_git(svc)

    monkeypatch.chdir(tmp_path)
    svc.cleanup("worktrees/RELATIVE")

    assert calls == [["worktree", "remove", str(wt_path)]]
    assert calls[0][-1] != "worktrees/RELATIVE"


def test_cleanup_status_and_remove_use_matched_path(tmp_path: Path, monkeypatch):
    """CX-02 — matched path authority: get_status i remove primaju matched path."""
    svc = _service(tmp_path)
    wt_path = svc.worktrees_dir / "RELATIVE"
    wt_path.mkdir(parents=True)
    svc.list_worktrees = lambda: [_info(str(wt_path))]

    seen_status: list[str] = []

    def fake_get_status(path):
        seen_status.append(path)
        return {"exists": True, "clean": True, "has_conflicts": False}

    svc.get_status = fake_get_status
    calls = _spy_git(svc)

    monkeypatch.chdir(tmp_path)
    svc.cleanup("worktrees/RELATIVE")

    assert seen_status == [str(wt_path)]
    assert calls == [["worktree", "remove", str(wt_path)]]
