"""Git state reader — čitanje i poređenje Git stanja repozitorijuma.

Koristi subprocess za git komande. Ne uvodi GitPython.
Vraća strukturisani GitState i GitChangeSet.
"""

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class GitChangeSet:
    """Rezultat poređenja dva Git stanja."""

    first_observation: bool = False
    commit_changed: bool = False
    branch_changed: bool = False
    dirty_state_changed: bool = False
    new_untracked_files: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    previous_commit_sha: str | None = None
    current_commit_sha: str | None = None
    previous_branch: str | None = None
    current_branch: str | None = None


@dataclass
class GitState:
    """Trenutno Git stanje repozitorijuma."""

    commit_sha: str | None = None
    branch: str | None = None
    is_dirty: bool = False
    changed_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    observed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "is_dirty": self.is_dirty,
            "changed_files": self.changed_files,
            "untracked_files": self.untracked_files,
            "observed_at": self.observed_at,
        }


class GitStateReader:
    """Čita Git stanje repozitorijuma i poredi sa prethodnim.

    Ne koristi GitPython — sve kroz subprocess.
    Za periodični polling, pozivalac koristi timer/scheduler.
    """

    def __init__(self, repo_path: str) -> None:
        self._repo = Path(repo_path)
        self._last_state: GitState | None = None

    @property
    def last_state(self) -> GitState | None:
        return self._last_state

    def poll_and_detect(self) -> tuple[GitState, GitChangeSet]:
        """Čita trenutno stanje i poredi sa prethodnim.

        Returns:
            (sveže_stanje, promene_u_odnosu_na_prethodno)
        """
        previous = self._last_state
        fresh = self._read_state()
        changes = self._compare(previous, fresh)
        self._last_state = fresh
        return fresh, changes

    def _read_state(self) -> GitState:
        """Čita trenutno Git stanje."""
        state = GitState(observed_at=datetime.now(tz=UTC).isoformat())

        state.commit_sha = self._run_git(["rev-parse", "HEAD"])
        state.branch = self._run_git(["branch", "--show-current"])

        # status --porcelain=v2 -z za sve promene (uključujući untracked)
        raw = self._run_git(["status", "--porcelain=v2", "-z"])
        state.is_dirty = bool(raw.strip())
        state.changed_files, state.untracked_files = self._parse_porcelain_v2(raw)

        return state

    def _compare(self, prev: GitState | None, fresh: GitState) -> GitChangeSet:
        """Poredi prethodno i sveže stanje."""
        if prev is None:
            return GitChangeSet(first_observation=True)

        return GitChangeSet(
            commit_changed=fresh.commit_sha is not None
            and prev.commit_sha is not None
            and fresh.commit_sha != prev.commit_sha,
            branch_changed=fresh.branch is not None
            and prev.branch is not None
            and fresh.branch != prev.branch,
            dirty_state_changed=fresh.is_dirty != prev.is_dirty,
            new_untracked_files=tuple(
                f for f in fresh.untracked_files if f not in prev.untracked_files
            ),
            changed_files=tuple(f for f in fresh.changed_files if f not in prev.changed_files),
            previous_commit_sha=prev.commit_sha,
            current_commit_sha=fresh.commit_sha,
            previous_branch=prev.branch,
            current_branch=fresh.branch,
        )

    @staticmethod
    def _parse_porcelain_v2(raw: str) -> tuple[list[str], list[str]]:
        """Parsira git status --porcelain=v2 -z izlaz.

        Vraća (tracked_changes, untracked_files).
        """
        changed: list[str] = []
        untracked: list[str] = []
        if not raw.strip():
            return changed, untracked

        entries = raw.split("\0")
        for entry in entries:
            if not entry.strip():
                continue
            parts = entry.split(" ", 1)
            if len(parts) < 2:
                continue
            status = parts[0]
            path = parts[1].strip()
            if status.startswith("?"):
                untracked.append(path)
            else:
                changed.append(path)
        return changed, untracked

    def _run_git(self, args: list[str]) -> str:
        """Pokreće git komandu i vraća stdout, ili prazan string pri grešci."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self._repo),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return ""
            return result.stdout
        except Exception:
            return ""
