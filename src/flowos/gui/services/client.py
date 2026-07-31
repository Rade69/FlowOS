"""GUI API klijent — HTTP i WebSocket komunikacija sa backendom.

Koristi QNetworkAccessManager za HTTP i QWebSocket za WS.
Nikad ne blokira GUI thread.
"""


class GuiApiClient:
    """API klijent za FlowOS backend.

    Sve metode su async — koriste Qt signale za povratne pozive.
    Implementira se u fazi 1-2 kada backend dobije stvarne endpoint-e.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9100") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    # Placeholder metode — implementirati u fazi 1
    # async def check_health(self) -> HealthResponse: ...
    # async def get_projects(self) -> list[ProjectResponse]: ...
    # async def create_project(self, data: ProjectCreate) -> ProjectResponse: ...
    # ...
