r"""CLI API klijent — httpx-based komunikacija sa backendom.

Kada backend nije dostupan, upisuje događaje u JSONL spool:
    %LOCALAPPDATA%\FlowOS\spool\<session-id>.jsonl

Svaki zapis ima idempotency ključ za siguran ponovni uvoz.
"""

from pathlib import Path


class CliApiClient:
    """API klijent za FlowOS backend iz CLI-ja.

    Koristi httpx za HTTP pozive. Pri nedostupnosti backend-a,
    upisuje u offline JSONL spool.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9100") -> None:
        self._base_url = base_url.rstrip("/")
        self._spool_dir = Path.home() / "AppData" / "Local" / "FlowOS" / "spool"

    @property
    def base_url(self) -> str:
        return self._base_url

    # Placeholder metode — implementirati u fazi 2
    # def register_session(self, data: SessionCreate) -> SessionResponse: ...
    # def end_session(self, session_id: str) -> SessionResponse: ...
    # def add_event(self, session_id: str, data: SessionEventCreate) -> ...: ...


__all__ = ["CliApiClient"]
