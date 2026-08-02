"""Watcher pipeline — filesystem događaji sa debounce-om.

Koristi watchdog biblioteku za praćenje create/modify/delete događaja.
Debounce 500ms, filtrira ignorisane foldere, emituje kroz queue.
"""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("flowos.watcher")


class ActivityEvent:
    """Normalizovan filesystem događaj."""

    def __init__(self, event_type: str, path: str, observed_at: float | None = None) -> None:
        self.event_type = event_type  # CREATED, MODIFIED, DELETED
        self.path = path
        self.observed_at = observed_at or time.time()


class WatcherPipeline:
    """Upravlja watchdog observer-om i debounce queue-om."""

    DEFAULT_IGNORE = {
        ".git",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".venv",
        "venv",
        "generated",
        "backups",
    }

    def __init__(
        self,
        callback: Callable[[ActivityEvent], None],
        debounce_ms: int = 500,
        ignore_patterns: set[str] | None = None,
    ) -> None:
        self._callback = callback
        self._debounce = debounce_ms / 1000.0
        self._ignore = ignore_patterns or self.DEFAULT_IGNORE
        self._observer: object | None = None  # watchdog Observer (object zbog mypy valid-type)
        self._pending: dict[str, ActivityEvent] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, repo_path: str) -> None:
        """Pokreće watchdog observer."""
        path = Path(repo_path)
        if not path.exists():
            raise FileNotFoundError(f"Putanja ne postoji: {repo_path}")
        if self._running:
            logger.warning("Watcher već pokrenut, preskačem.")
            return
        handler = _WatchdogHandler(self._on_event)
        self._observer = Observer()
        self._observer.schedule(handler, str(path), recursive=True)
        self._observer.start()
        self._running = True
        logger.info("Watcher pokrenut: %s", repo_path)

    def stop(self) -> None:
        """Bezbedno zaustavlja observer, otkazuje timer, flush-uje događaje."""
        if not self._running:
            return
        self._running = False
        if self._observer:
            self._observer.stop()  # type: ignore[attr-defined]
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            pending = list(self._pending.values())
            self._pending.clear()
        for event in pending:
            self._safe_callback(event)
        if self._observer:
            self._observer.join(timeout=5)  # type: ignore[attr-defined]
            self._observer = None
        logger.info("Watcher zaustavljen.")

    def _on_event(self, event_type: str, file_path: str) -> None:
        """Prima događaj od watchdog-a, primenjuje debounce."""
        if self._should_ignore(file_path):
            return

        with self._lock:
            self._pending[file_path] = ActivityEvent(event_type, file_path)

            if self._timer:
                self._timer.cancel()

            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.start()

    def _flush(self) -> None:
        """Emituje sve nakupljene događaje."""
        with self._lock:
            events = list(self._pending.values())
            self._pending.clear()
            self._timer = None
        for event in events:
            self._safe_callback(event)

    def _safe_callback(self, event: ActivityEvent) -> None:
        try:
            self._callback(event)
        except Exception:
            logger.exception("Watcher callback nije uspio za %s", event.path)

    def _should_ignore(self, file_path: str) -> bool:
        """Proverava da li putanja sadrži ignorisani folder."""
        parts = Path(file_path).parts
        return any(p in self._ignore for p in parts)


class _WatchdogHandler(FileSystemEventHandler):
    """Prevodi watchdog događaje u ActivityEvent."""

    def __init__(self, callback: Callable[[str, str], None]) -> None:
        self._callback = callback

    def on_created(self, event):
        if not event.is_directory:
            self._callback("CREATED", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._callback("MODIFIED", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._callback("DELETED", event.src_path)
