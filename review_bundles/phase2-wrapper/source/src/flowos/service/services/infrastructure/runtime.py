"""FlowOS Runtime Manager — single-instance lock, descriptor, port.

Upravlja životnim ciklusom servisa:
- Single-instance mutex (samo jedan flowos-service u jednom trenutku)
- Runtime descriptor JSON za GUI/CLI otkrivanje
- Pronalazak slobodnog loopback porta
"""

import json
import os
import socket
import sys
import uuid
from ctypes import windll, wintypes
from typing import Any

from flowos.service.services.infrastructure.app_paths import get_runtime_dir

kernel32 = windll.kernel32

if sys.platform != "win32":
    import fcntl  # pragma: no cover


class PortAlreadyInUseError(RuntimeError):
    """Zadati port je već zauzet."""


class InstanceAlreadyRunningError(RuntimeError):
    """Druga instanca flowos-service već radi."""


class RuntimeManager:
    """Upravlja runtime stanjem FlowOS servisa.

    Odgovornosti:
    - Single-instance lock (mutex na Windows, flock na Unix)
    - Runtime descriptor JSON
    - Pronalazak slobodnog loopback porta
    """

    MUTEX_NAME = "Global\\FlowOS_Service_Mutex"
    DESCRIPTOR_DIR = get_runtime_dir()
    DESCRIPTOR_FILE = DESCRIPTOR_DIR / "service.json"
    DEFAULT_PORT = 9100

    def __init__(self) -> None:
        self._mutex_handle: Any = None
        self._port: int | None = None
        self._pid: int = os.getpid()

    # ── Single-instance lock ──────────────────────────────

    def acquire_lock(self) -> None:
        """Pokušava da zauzme single-instance mutex.

        Raises:
            InstanceAlreadyRunningError: ako je druga instanca već aktivna.
        """
        if sys.platform == "win32":
            self._acquire_windows_mutex()
        else:
            self._acquire_unix_lock()

    def _acquire_windows_mutex(self) -> None:
        """Windows: CreateMutex + GetLastError."""
        handle = kernel32.CreateMutexW(None, wintypes.BOOL(True), self.MUTEX_NAME)
        if handle == 0:
            raise InstanceAlreadyRunningError("Ne mogu da kreiram mutex")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            raise InstanceAlreadyRunningError(
                "FlowOS servis je već pokrenut. Samo jedna instanca je dozvoljena."
            )
        self._mutex_handle = handle

    def _acquire_unix_lock(self) -> None:
        """Unix: flock na lock fajlu."""
        lock_dir = self.DESCRIPTOR_DIR
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_fd = open(lock_dir / ".service.lock", "w")  # noqa: SIM115
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            raise InstanceAlreadyRunningError(
                "FlowOS servis je već pokrenut. Samo jedna instanca je dozvoljena."
            ) from err

    def release_lock(self) -> None:
        """Oslobađa single-instance mutex."""
        if sys.platform == "win32":
            if self._mutex_handle:
                kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = None
        else:
            if hasattr(self, "_lock_fd"):
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()

    # ── Port ───────────────────────────────────────────────

    def find_free_port(self, start: int = DEFAULT_PORT) -> int:
        """Pronalazi prvi slobodan port počevši od start_port.

        Raises:
            PortAlreadyInUseError: ako nijedan port nije slobodan u opsegu start..start+99.
        """
        for port in range(start, start + 100):
            if self._port_is_free(port):
                self._port = port
                return port
        raise PortAlreadyInUseError(f"Nijedan port nije slobodan u opsegu {start}-{start + 99}")

    @staticmethod
    def _port_is_free(port: int) -> bool:
        """Proverava da li je port slobodan na loopback interfejsu."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    # ── Runtime descriptor ──────────────────────────────────

    def write_descriptor(self, port: int) -> None:
        """Upisuje runtime descriptor JSON fajl atomski (tmp → rename)."""
        self.DESCRIPTOR_DIR.mkdir(parents=True, exist_ok=True)
        descriptor = {
            "pid": self._pid,
            "port": port,
            "version": "0.1.0",
            "api_version": 1,
            "instance_id": str(uuid.uuid4()),
            "started_at": self._utcnow_iso(),
            "data_directory": str(self.DESCRIPTOR_DIR.parent / "data"),
            "status": "running",
        }
        tmp = self.DESCRIPTOR_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(descriptor, indent=2))
        tmp.replace(self.DESCRIPTOR_FILE)

    def delete_descriptor(self) -> None:
        """Briše runtime descriptor JSON fajl (graceful shutdown)."""
        import contextlib

        with contextlib.suppress(OSError):
            self.DESCRIPTOR_FILE.unlink(missing_ok=True)

    @staticmethod
    def _utcnow_iso() -> str:
        from datetime import UTC, datetime

        return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def port(self) -> int | None:
        return self._port

    @property
    def pid(self) -> int:
        return self._pid
