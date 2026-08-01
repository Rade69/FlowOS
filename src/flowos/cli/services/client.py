r"""CLI API klijent — httpx-based komunikacija sa backendom.

Kada backend nije dostupan, upisuje događaje u JSONL spool:
    %LOCALAPPDATA%\FlowOS\spool\<session-id>.jsonl

Svaki zapis ima idempotency ključ za siguran ponovni uvoz.
"""


import httpx


class CliApiClient:
    """API klijent za FlowOS backend iz CLI-ja."""

    def __init__(self, base_url: str = "http://127.0.0.1:9100") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    def get(self, path: str) -> dict | list:
        """GET zahtev ka API-ju."""
        r = httpx.get(f"{self._base_url}{path}", timeout=5.0)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, data: dict) -> dict:
        """POST zahtev ka API-ju."""
        r = httpx.post(f"{self._base_url}{path}", json=data, timeout=5.0)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str) -> dict:
        """DELETE zahtev ka API-ju."""
        r = httpx.delete(f"{self._base_url}{path}", timeout=5.0)
        r.raise_for_status()
        return r.json()
