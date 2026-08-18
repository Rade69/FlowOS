"""FlowOS strukturisani lokalni logovi.

Koristi Python logging sa:
- Rotirajućim fajl handlerom (10 MB max, 3 backup-a)
- Konzolnim handlerom u dev modu
- JSON formatom za mašinsko parsiranje (opciono)
"""

import logging
import sys
from pathlib import Path

from flowos.service.services.infrastructure.dir_security import ensure_private_directory


def setup_logging(
    *,
    level: int = logging.INFO,
    log_dir: Path | None = None,
    console: bool = True,
    json_format: bool = False,
) -> logging.Logger:
    """Konfiguriše FlowOS root logger.

    Args:
        level: Log nivo (default: INFO)
        log_dir: Direktorijum za log fajlove (default: %LOCALAPPDATA%/FlowOS/logs)
        console: Da li da emituje logove na stdout (dev mod)
        json_format: Da li da koristi JSON format (lakše parsiranje)

    Returns:
        Root logger za FlowOS.
    """
    used_default_log_dir = log_dir is None
    if log_dir is None:
        import os

        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        log_dir = base / "FlowOS" / "logs"

    if used_default_log_dir:
        # FLOW-1108: default lokacija se hardenuje pri svakom pozivu,
        # uključujući već postojeće instalacije. Eksplicitno prosleđen
        # `log_dir` (npr. budući test override) ostaje van FlowOS/temp
        # allowlist provjere i zadržava plain mkdir ponašanje.
        ensure_private_directory(log_dir)
    else:
        log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("flowos")
    root.setLevel(level)
    root.handlers.clear()

    # Formater
    if json_format:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(  # type: ignore[assignment]
            fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # Fajl handler (rotirajući)
    try:
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(
            log_dir / "flowos-service.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except ImportError:
        # Fallback: običan FileHandler
        fh = logging.FileHandler(log_dir / "flowos-service.log", encoding="utf-8")  # type: ignore[assignment]
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)

    # Konzolni handler (dev mod)
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root.addHandler(ch)

    return root


class _JsonFormatter(logging.Formatter):
    """JSON formater — lak za parsiranje alatima."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import UTC, datetime

        payload = {
            "ts": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exc"] = str(record.exc_info[1])
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """Vraća logger za dati modul."""
    return logging.getLogger(f"flowos.{name}")
