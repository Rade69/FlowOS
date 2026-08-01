"""Git polling service — periodična provera Git stanja.

Koristi subprocess za git komande. Ne uvodi GitPython.
Polling interval: 30s. Upoređuje sa poslednjim poznatim stanjem.
"""

import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class GitState:
    """Trenutno Git stanje repozitorijuma."""

    commit_sha: str | None = None
    branch: str | None = None
    status_porcelain: str = ""
    changed_files: list[str] = field(default_factory=list)
    is_dirty: bool = False
    observed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "status_porcelain": self.status_porcelain,
            "changed_files": self.changed_files,
            "is_dirty": self.is_dirty,
            "observed_at": self.observed_at,
        }


class GitPoller:
    """Periodično proverava Git stanje repozitorijuma.

    Ne koristi GitPython — sve kroz subprocess.
    Interval: 30 sekundi.
    """

    def __init__(self, repo_path: str, interval: float = 30.0) -> None:
        self._repo = Path(repo_path)
        self._interval = interval
        self._last_state: GitState | None = None
        self._running = False

    @property
    def last_state(self) -> GitState | None:
        return self._last_state

    def poll(self) -> GitState:
        """Izvršava git komande i vraća trenutno stanje.

        Komande:
        - git rev-parse HEAD
        - git branch --show-current
        - git status --porcelain=v2
        - git diff --name-only HEAD (ako je dirty)
        """
        state = GitState(observed_at=datetime.now(tz=UTC).isoformat())

        try:
            state.commit_sha = self._run_git(["rev-parse", "HEAD"]).strip()
        except Exception:
            state.commit_sha = None

        try:
            state.branch = self._run_git(["branch", "--show-current"]).strip()
        except Exception:
            state.branch = None

        try:
            state.status_porcelain = self._run_git(["status", "--porcelain=v2"])
        except Exception:
            state.status_porcelain = ""

        state.is_dirty = bool(state.status_porcelain.strip())

        if state.is_dirty:
            try:
                files = self._run_git(["diff", "--name-only", "HEAD"])
                state.changed_files = [f for f in files.split("\n") if f]
            except Exception:
                state.changed_files = []

        self._last_state = state
        return state

    def detect_changes(self, fresh: GitState) -> dict:
        """Upoređuje sveže stanje sa poslednjim. Vraća promene."""
        prev = self._last_state
        changes = {"new_commits": False, "branch_changed": False, "new_dirty": False, "details": ""}

        if not prev:
            changes["details"] = "Prvo snimanje stanja."
            return changes

        if fresh.commit_sha and prev.commit_sha and fresh.commit_sha != prev.commit_sha:
            changes["new_commits"] = True
            changes["details"] += f"Novi commit: {prev.commit_sha[:8]} → {fresh.commit_sha[:8]}. "

        if fresh.branch and prev.branch and fresh.branch != prev.branch:
            changes["branch_changed"] = True
            changes["details"] += f"Granica promijenjena: {prev.branch} → {fresh.branch}. "

        if fresh.is_dirty and not prev.is_dirty:
            changes["new_dirty"] = True
            changes["details"] += f"Radno stablo sa neupisanim promjenama ({len(fresh.changed_files)} fajlova). "

        return changes

    def _run_git(self, args: list[str]) -> str:
        """Pokreće git komandu i vraća stdout."""
        result = subprocess.run(
            ["git"] + args,
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout