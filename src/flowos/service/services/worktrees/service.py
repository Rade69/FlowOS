"""Worktree Service — upravljanje Git worktree-jima.

Pravila:
- Naming: branch = flow/<task-id>-<slug>, worktree = <repo-parent>/worktrees/<task-id>/
- Jedan writable worktree = najviše jedna writer sesija
- Integracija je uvek korisnička akcija — nema automatskog merge-a
- Napušteni worktree se ne briše pre retention perioda (7-30 dana)
"""

import contextlib
import logging
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("flowos.worktree")


class WorktreeError(Exception):
    """Greška pri radu sa worktree-jem."""


class WorktreeExistsError(WorktreeError):
    """Worktree već postoji na datoj putanji."""


class WorktreeInUseError(WorktreeError):
    """Worktree već ima aktivnu writer sesiju."""


@dataclass
class WorktreeInfo:
    """Informacije o jednom worktree-ju."""

    path: str
    branch: str
    commit_sha: str
    is_bare: bool = False
    is_detached: bool = False
    is_main: bool = False  # glavni worktree (ne može se obrisati)

    # FlowOS metapodaci
    task_id: str | None = None
    session_id: str | None = None
    status: str = "UNKNOWN"  # CLEAN, DIRTY, CONFLICT, INTEGRATED
    created_at: str | None = None
    last_activity_at: str | None = None


class WorktreeService:
    """Upravljanje Git worktree-jima za izolaciju sesija."""

    DEFAULT_RETENTION_DAYS = 7

    def __init__(self, repo_path: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> None:
        self._repo = Path(repo_path).resolve()
        self._retention = timedelta(days=retention_days)

        if not self._repo.exists():
            raise WorktreeError(f"Repozitorijum ne postoji: {self._repo}")

    @property
    def repo_path(self) -> str:
        return str(self._repo)

    @property
    def worktrees_dir(self) -> Path:
        """Direktorijum za worktree-je — pored repoa."""
        return self._repo.parent / "worktrees"

    # ── Create ─────────────────────────────────────────────────

    def create(
        self,
        task_id: str,
        slug: str = "",
        *,
        base_branch: str = "",
    ) -> WorktreeInfo:
        """Kreira novi worktree za zadatak.

        Args:
            task_id: ID zadatka (npr. FLOW-401).
            slug: Kratak opis (npr. 'worktree-service').
            base_branch: Grana sa koje se grana. Ako nije data,
                koristi se prva dostupna od: main, master.

        Returns:
            WorktreeInfo sa podacima o kreiranom worktree-ju.

        Raises:
            WorktreeExistsError: Ako worktree već postoji.
            WorktreeError: Ako kreiranje ne uspe.
        """
        branch_name = self._make_branch_name(task_id, slug)
        worktree_path = self.worktrees_dir / task_id

        if worktree_path.exists():
            raise WorktreeExistsError(
                f"Worktree već postoji: {worktree_path}. "
                f"Koristite list() za pregled ili cleanup() za uklanjanje."
            )

        # Auto-detekcija bazne grane
        if not base_branch:
            base_branch = self._detect_default_branch()

        # Osiguraj da worktrees_dir postoji
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Kreiraj worktree sa bazne grane
        try:
            self._git(
                [
                    "worktree",
                    "add",
                    "-b",
                    branch_name,
                    str(worktree_path),
                    base_branch,
                ]
            )
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"Neuspelo kreiranje worktree-ja: {e.stderr}") from e

        logger.info(
            "Worktree kreiran: %s (branch=%s, base=%s)",
            worktree_path,
            branch_name,
            base_branch,
        )

        return self._build_info(str(worktree_path), branch_name, task_id=task_id)

    # ── List ───────────────────────────────────────────────────

    def list_worktrees(self) -> list[WorktreeInfo]:
        """Vraća sve worktree-je za ovaj repo.

        Koristi `git worktree list --porcelain`.
        """
        raw = self._git(["worktree", "list", "--porcelain"])
        return self._parse_worktree_list(raw)

    def list_flowos_worktrees(self) -> list[WorktreeInfo]:
        """Vraća samo FlowOS worktree-je (u worktrees_dir)."""
        all_wt = self.list_worktrees()
        wt_dir = str(self.worktrees_dir).replace("\\", "/")
        return [
            wt
            for wt in all_wt
            if wt.path.replace("\\", "/").startswith(wt_dir) and not wt.is_main
        ]

    # ── Status ─────────────────────────────────────────────────

    def get_status(self, worktree_path: str) -> dict[str, Any]:
        """Vraća detaljan status worktree-ja.

        Returns:
            dict sa: clean, branch, commit, changed_files, untracked_files, has_conflicts.
        """
        path = Path(worktree_path)
        if not path.exists():
            return {"exists": False, "clean": False, "error": "Worktree ne postoji"}

        try:
            status_raw = self._git(
                ["status", "--porcelain=v2", "-z"], cwd=str(path)
            )
            branch = self._git(
                ["branch", "--show-current"], cwd=str(path)
            )
            commit = self._git(
                ["rev-parse", "HEAD"], cwd=str(path)
            )
        except subprocess.CalledProcessError as e:
            return {"exists": True, "clean": False, "error": str(e.stderr)}

        changed: list[str] = []
        untracked: list[str] = []
        has_conflicts = False

        if status_raw.strip():
            entries = status_raw.split("\0")
            for entry in entries:
                entry = entry.strip()
                if not entry:
                    continue
                if entry.startswith("? "):
                    untracked.append(entry[2:])
                elif entry.startswith("! "):
                    continue
                elif entry[0] in ("1", "2"):
                    parts = entry.split(" ")
                    if entry[0] == "1" and len(parts) >= 9:
                        path_str = " ".join(parts[8:])
                        changed.append(path_str)
                        # XY sadrži U za konflikt (npr. UU, AU, UA)
                        if len(parts) >= 2 and "U" in parts[1]:
                            has_conflicts = True

        return {
            "exists": True,
            "clean": len(changed) == 0 and len(untracked) == 0,
            "branch": branch.strip(),
            "commit": commit.strip(),
            "changed_files": changed,
            "untracked_files": untracked,
            "has_conflicts": has_conflicts,
        }

    # ── Cleanup ────────────────────────────────────────────────

    def can_cleanup(self, worktree_path: str) -> tuple[bool, str]:
        """Proverava da li worktree može biti obrisan.

        Returns:
            (može, razlog_zašto_ne).
        """
        info = self._find_worktree(worktree_path)
        if not info:
            return False, "Worktree ne postoji."

        if info.is_main:
            return False, "Glavni worktree se ne može obrisati."

        status = self.get_status(worktree_path)
        if status.get("has_conflicts"):
            return False, "Worktree ima konflikte — prvo ih razrešite."

        return True, ""

    def cleanup(self, worktree_path: str, force: bool = False) -> None:
        """Uklanja worktree.

        Args:
            worktree_path: Putanja do worktree-ja.
            force: Ako True, koristi --force.

        Raises:
            WorktreeError: Ako brisanje ne uspe.
        """
        can, reason = self.can_cleanup(worktree_path)
        if not can and not force:
            raise WorktreeError(f"Worktree ne može biti obrisan: {reason}")

        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(worktree_path)

        try:
            self._git(args)
            logger.info("Worktree uklonjen: %s", worktree_path)
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"Neuspelo uklanjanje worktree-ja: {e.stderr}") from e

    def prune(self) -> list[str]:
        """Čisti nevažeće worktree reference.

        Returns:
            Lista uklonjenih referenci.
        """
        try:
            result = self._git(["worktree", "prune"])
            return [line for line in result.split("\n") if line.strip()]
        except subprocess.CalledProcessError:
            return []

    # ── Integracija (priprema) ─────────────────────────────────

    def get_diff_to_base(self, worktree_path: str, base_branch: str = "main") -> str:
        """Vraća diff worktree-ja u odnosu na baznu granu."""
        try:
            self._git(["fetch", "origin", base_branch])
        except subprocess.CalledProcessError:
            pass  # fetch može pasti ako nema remote-a

        try:
            return self._git(
                ["diff", f"origin/{base_branch}"],
                cwd=worktree_path,
            )
        except subprocess.CalledProcessError:
            return self._git(
                ["diff", base_branch],
                cwd=worktree_path,
            )

    def get_changed_files(self, worktree_path: str, base_branch: str = "main") -> list[str]:
        """Vraća listu izmenjenih fajlova u odnosu na baznu granu."""
        try:
            raw = self._git(
                ["diff", "--name-status", f"origin/{base_branch}"],
                cwd=worktree_path,
            )
        except subprocess.CalledProcessError:
            raw = self._git(
                ["diff", "--name-status", base_branch],
                cwd=worktree_path,
            )
        return [line for line in raw.split("\n") if line.strip()]

    # ── Retention ────────────────────────────────────────────────

    def get_retention_status(self, worktree_path: str) -> dict[str, Any]:
        """Proverava retention status worktree-ja.

        Returns:
            dict sa: can_cleanup, age_days, retention_days, remaining_days, reason.
        """
        info = self._find_worktree(worktree_path)
        if not info:
            return {"can_cleanup": False, "reason": "Worktree ne postoji"}

        if info.is_main:
            return {"can_cleanup": False, "reason": "Glavni worktree"}

        age = None
        if info.created_at:
            created = datetime.fromisoformat(info.created_at)
            age = (datetime.now(tz=UTC) - created).days

        remaining = max(0, self._retention.days - (age or 0))

        return {
            "can_cleanup": age is not None and age >= self._retention.days,
            "age_days": age,
            "retention_days": self._retention.days,
            "remaining_days": remaining,
            "reason": (
                ""
                if (age is not None and age >= self._retention.days)
                else f"Retention: {remaining} dana preostalo"
            ),
        }

    def list_abandoned(self) -> list[WorktreeInfo]:
        """Vraća FlowOS worktree-je spremne za cleanup (prošao retention)."""
        flowos_wt = self.list_flowos_worktrees()
        abandoned = []
        for wt in flowos_wt:
            retention = self.get_retention_status(wt.path)
            if retention["can_cleanup"]:
                abandoned.append(wt)
        return abandoned

    # ── Integracija ─────────────────────────────────────────────

    def prepare_integration(self, worktree_path: str, base_branch: str = "main") -> dict[str, Any]:
        """Priprema integraciju: diff, changed files, verify, conflict check.

        Returns:
            dict sa: diff, changed_files, has_conflicts, base_branch, worktree_commit.
        """
        status = self.get_status(worktree_path)
        diff = self.get_diff_to_base(worktree_path, base_branch)
        changed = self.get_changed_files(worktree_path, base_branch)

        return {
            "worktree_path": worktree_path,
            "base_branch": base_branch,
            "worktree_commit": status.get("commit", ""),
            "clean": status.get("clean", False),
            "has_conflicts": status.get("has_conflicts", False),
            "diff": diff[:10000],
            "changed_files": changed,
            "changed_count": len(changed),
        }

    # ── Pomoćne metode ────────────────────────────────────────

    @staticmethod
    def _make_branch_name(task_id: str, slug: str) -> str:
        """Pravi ime grane po konvenciji: flow/<task-id>-<slug>."""
        safe_slug = slug.lower().replace(" ", "-")[:50] if slug else "impl"
        return f"flow/{task_id}-{safe_slug}"

    def _build_info(
        self, path: str, branch: str, task_id: str | None = None
    ) -> WorktreeInfo:
        """Pravi WorktreeInfo iz putanje i grane."""
        commit = ""
        with contextlib.suppress(subprocess.CalledProcessError):
            commit = self._git(["rev-parse", "HEAD"], cwd=path).strip()

        return WorktreeInfo(
            path=path,
            branch=branch,
            commit_sha=commit,
            task_id=task_id,
            status="CLEAN",
            created_at=datetime.now(tz=UTC).isoformat(),
        )

    def _find_worktree(self, path: str) -> WorktreeInfo | None:
        """Pronalazi worktree po putanji."""
        worktrees = self.list_worktrees()
        for wt in worktrees:
            if wt.path == path or wt.path.startswith(path):
                return wt
        return None

    def _parse_worktree_list(self, raw: str) -> list[WorktreeInfo]:
        """Parsira `git worktree list --porcelain` izlaz."""
        worktrees: list[WorktreeInfo] = []
        current: dict[str, str] = {}

        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(self._dict_to_info(current))
                    current = {}
                continue

            if " " in line:
                key, value = line.split(" ", 1)
                current[key] = value

        if current:
            worktrees.append(self._dict_to_info(current))

        return worktrees

    def _dict_to_info(self, data: dict[str, str]) -> WorktreeInfo:
        """Konvertuje dict iz porcelain izlaza u WorktreeInfo."""
        path = data.get("worktree", "")
        branch = data.get("branch", "").replace("refs/heads/", "")
        commit = data.get("HEAD", "")
        is_bare = data.get("bare", "") == "true"
        is_detached = data.get("detached", "") == "true"

        # Detektuj glavni worktree (nije u worktrees_dir)
        wt_dir = str(self.worktrees_dir).replace("\\", "/")
        is_main = not path.replace("\\", "/").startswith(wt_dir)

        # Izvuci task_id iz putanje (worktrees/<task_id>)
        task_id = None
        if not is_main:
            parts = Path(path).parts
            if len(parts) >= 2 and parts[-2] == "worktrees":
                task_id = parts[-1]

        return WorktreeInfo(
            path=path,
            branch=branch,
            commit_sha=commit,
            is_bare=is_bare,
            is_detached=is_detached,
            is_main=is_main,
            task_id=task_id,
        )

    def _detect_default_branch(self) -> str:
        """Detektuje podrazumevanu granu (main ili master)."""
        for candidate in ("main", "master"):
            try:
                self._git(["rev-parse", "--verify", candidate])
                return candidate
            except subprocess.CalledProcessError:
                continue
        return "main"  # fallback

    def _git(self, args: list[str], cwd: str | None = None) -> str:
        """Pokreće git komandu i vraća stdout."""
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or str(self._repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                ["git"] + args,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result.stdout
