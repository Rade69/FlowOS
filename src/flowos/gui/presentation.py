"""GUI prezentacioni helperi — formatiranje bez API/ORM zavisnosti.

Funkcije za formatiranje vremena, putanja, SHA vrednosti.
Testabilno, bez poslovne logike.
"""

from datetime import UTC, datetime


def format_relative_time(value: str | datetime | None) -> str:
    """Formatira ISO timestamp u relativno vreme (npr. 'prije 3m', 'upravo')."""
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        delta = datetime.now(tz=UTC) - value
        seconds = int(delta.total_seconds())
        if seconds < 0:
            return "—"
        if seconds < 60:
            return "upravo"
        if seconds < 3600:
            return f"prije {seconds // 60}m"
        if seconds < 86400:
            return f"prije {seconds // 3600}h"
        return f"prije {seconds // 86400}d"
    except Exception:
        return "—"


def format_duration(started_at: str | None, ended_at: str | None = None) -> str:
    """Formatira trajanje između dva ISO timestampa."""
    if not started_at:
        return "—"
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = (
            datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            if ended_at
            else datetime.now(tz=UTC)
        )
        seconds = int((end - start).total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m"
        if seconds < 86400:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m"
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d {h}h"
    except Exception:
        return "—"


def short_sha(value: str | None, length: int = 8) -> str:
    """Skraćuje SHA hash na dato dužinu."""
    if not value:
        return "—"
    return value[:length]


def short_path(value: str | None, max_length: int = 40) -> str:
    """Skraćuje putanju fajla."""
    if not value:
        return "—"
    if len(value) <= max_length:
        return value
    return "..." + value[-(max_length - 3) :]


def safe_text(value, fallback: str = "—") -> str:
    """Vraća tekst ili fallback ako je prazno/None."""
    if not value:
        return fallback
    return str(value)


def status_badge_text(status: str) -> str:
    """Prevodi status na srpski za badge prikaz."""
    labels = {
        "ACCEPTED": "Prihvaćeno",
        "VERIFIED": "Provjereno",
        "IMPLEMENTED": "Implementirano",
        "IN_PROGRESS": "U toku",
        "BLOCKED": "Blokirano",
        "NOT_STARTED": "Nije započeto",
    }
    return labels.get(status, status)
