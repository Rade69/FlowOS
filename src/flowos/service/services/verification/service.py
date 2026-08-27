"""Verification Service — pokretanje i praćenje verify.py skripti.

Koristi sys.executable (projektni Python interpreter), nikada generički "python".
Svaki verify run čuva trajni artefakt u artifacts/verification/<id>/.
"""

import hashlib
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from flowos.service.services.infrastructure.redaction import redact_text


@dataclass
class VerificationResult:
    """Rezultat pokretanja verify.py."""

    artifact_id: str
    verify_path: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    success: bool  # exit_code == 0
    verified_at: str  # ISO timestamp
    artifact_path: str | None = None  # putanja do trajnog artefakta


class ArtifactStore:
    """Čuva verify artefakte na disk.

    Struktura: artifacts/verification/<verification-id>/
               ├── command.txt
               ├── stdout.txt
               ├── stderr.txt
               └── metadata.json
    """

    def __init__(self, base_path: str | None = None) -> None:
        if base_path is None:
            base_path = str(
                Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "artifacts"
            )
        self._base = Path(base_path)

    def save(
        self,
        verification_id: str,
        command: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_seconds: float,
        started_at: str,
        finished_at: str,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        working_directory: str = "",
        timed_out: bool = False,
    ) -> str:
        """Atomski čuva verify artefakt. Vraća putanju do direktorijuma."""
        # Path traversal zaštita
        if ".." in verification_id or "/" in verification_id or "\\" in verification_id:
            raise ValueError(f"Neispravan verification_id: {verification_id}")

        # Ograničenje veličine izlaza (max 1MB po fajlu).
        # FLOW-1109: subprocess stdout/stderr/command prolaze redaction boundary
        # PRIJE trajnog upisa u FlowOS-generisan artifact (verification dir).
        max_size = 1_000_000
        stdout = redact_text(stdout)[:max_size]
        stderr = redact_text(stderr)[:max_size]
        command = redact_text(command)
        artifact_dir = self._base / "verification" / verification_id
        tmp_dir = self._base / "verification" / f".tmp_{verification_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        (tmp_dir / "command.txt").write_text(command, encoding="utf-8")
        (tmp_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (tmp_dir / "stderr.txt").write_text(stderr, encoding="utf-8")

        # metadata.json
        metadata = {
            "artifact_id": verification_id,
            "session_id": session_id,
            "project_id": project_id,
            "command": command,
            "working_directory": working_directory,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int(duration_seconds * 1000),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "status": "PASS" if exit_code == 0 else "FAIL",
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "tool_version": "0.1.0",
            "python_executable": sys.executable,
        }
        (tmp_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Atomski rename
        if artifact_dir.exists():
            import shutil

            shutil.rmtree(artifact_dir)
        tmp_dir.rename(artifact_dir)

        return str(artifact_dir)


class VerificationService:
    """Pokreće scripts/verify.py i interpretira rezultat."""

    DEFAULT_VERIFY_PATH = "scripts/verify.py"
    DEFAULT_TIMEOUT = 300  # 5 minuta

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout_seconds

    def find_verify_script(self, repo_path: str) -> str | None:
        """Proverava da li repo ima scripts/verify.py.

        Vraća apsolutnu putanju ako postoji, inače None.
        """
        verify_path = Path(repo_path) / self.DEFAULT_VERIFY_PATH
        if verify_path.is_file():
            return str(verify_path)
        return None

    def run_verify(
        self,
        repo_path: str,
        verify_path: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> VerificationResult:
        """Pokreće verify.py u zadatom repou i čuva trajni artefakt.

        Args:
            repo_path: Putanja do repozitorijuma.
            verify_path: Eksplicitna putanja do verify skripte.
            session_id: Opcioni ID sesije za metadata.
            project_id: Opcioni ID projekta za metadata.

        Returns:
            VerificationResult sa svim detaljima i putanjom do artefakta.
        """
        artifact_id = str(uuid.uuid4())

        if verify_path is None:
            verify_path = str(Path(repo_path) / self.DEFAULT_VERIFY_PATH)

        verify_file = Path(verify_path)
        if not verify_file.is_file():
            return VerificationResult(
                artifact_id=artifact_id,
                verify_path=verify_path,
                exit_code=-1,
                stdout="",
                stderr=f"Verify skripta nije pronađena: {verify_path}",
                duration_seconds=0,
                timed_out=False,
                success=False,
                verified_at=datetime.now(tz=UTC).isoformat(),
            )

        started = datetime.now(tz=UTC)
        started_at = started.isoformat()
        command = f"{sys.executable} {verify_file}"

        try:
            result = subprocess.run(
                [sys.executable, str(verify_file)],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            timed_out = False
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            stdout = ""
            stderr = f"Timeout: verify.py nije završio u roku od {self._timeout}s."
            exit_code = -1

        duration = (datetime.now(tz=UTC) - started).total_seconds()
        finished_at = datetime.now(tz=UTC).isoformat()

        # Sačuvaj trajni artefakt
        artifact_path = None
        try:
            store = ArtifactStore()
            artifact_path = store.save(
                verification_id=artifact_id,
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=duration,
                started_at=started_at,
                finished_at=finished_at,
                session_id=session_id,
                project_id=project_id,
                working_directory=str(repo_path),
                timed_out=timed_out,
            )
        except Exception:
            import logging

            logging.getLogger("flowos.verification").exception(
                "Greška pri čuvanju verify artefakta %s", artifact_id
            )

        return VerificationResult(
            artifact_id=artifact_id,
            verify_path=verify_path,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
            success=exit_code == 0,
            verified_at=finished_at,
            artifact_path=artifact_path,
        )
