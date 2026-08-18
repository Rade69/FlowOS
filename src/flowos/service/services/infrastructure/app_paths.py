"""FlowOS AppPaths — centralni izvor svih putanja aplikacije.

Jedan modul za sve putanje. Svi moduli moraju koristiti ovaj modul
umesto direktnog konstruisanja putanja kroz Path.home() ili os.environ.
"""

import os
from pathlib import Path


def _get_local_appdata() -> Path:
    """Vraća %LOCALAPPDATA% ili ekvivalent."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local)
    return Path.home() / "AppData" / "Local"


_BASE = _get_local_appdata() / "FlowOS"


def get_flowos_root() -> Path:
    """%LOCALAPPDATA%/FlowOS — korijen svih FlowOS-owned application-data putanja."""
    return _BASE


def get_runtime_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/runtime/ — runtime descriptor i lock fajlovi."""
    return _BASE / "runtime"


def get_data_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/data/ — SQLite baza."""
    return _BASE / "data"


def get_logs_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/logs/ — log fajlovi."""
    return _BASE / "logs"


def get_artifacts_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/artifacts/ — veliki artefakti."""
    return _BASE / "artifacts"


def get_spool_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/spool/ — offline JSONL spool."""
    return _BASE / "spool"


def get_backups_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/backups/ — dnevni backup baze."""
    return _BASE / "backups"


def get_settings_dir() -> Path:
    """%LOCALAPPDATA%/FlowOS/settings/ — korisničke postavke."""
    return _BASE / "settings"


def ensure_directories() -> None:
    """Kreira sve potrebne direktorijume."""
    for d in [
        get_runtime_dir(),
        get_data_dir(),
        get_logs_dir(),
        get_artifacts_dir(),
        get_spool_dir(),
        get_backups_dir(),
        get_settings_dir(),
    ]:
        d.mkdir(parents=True, exist_ok=True)
