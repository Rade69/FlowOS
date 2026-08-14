"""FLOW-1107 — WebSocket auth boundary testovi.

Dokazuje da /ws zahtijeva possession trenutnog instance tokena PRIJE nego
što konekcija postane aktivan FlowOS event klijent, i da se token šalje
kroz Authorization header, nikad kroz URL query string.
"""

import contextlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.websockets import WebSocketDisconnect

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.persistence.base import Base


class _NoOpRuntimeManager:
    """RuntimeManager stub sa fiksnim test tokenom."""

    TOKEN = "ws-test-token"

    def __init__(self):
        self.pid = os.getpid()
        self.port = 9102
        self.token = self.TOKEN

    def acquire_lock(self) -> None:
        pass

    def release_lock(self) -> None:
        pass

    def delete_descriptor(self) -> None:
        pass


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def app(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return create_app(_NoOpRuntimeManager(), engine=engine)


class TestWebSocketAuth:
    def test_websocket_without_token_rejected(self, app):
        """A: WebSocket bez tokena — nikad ne postaje aktivan event klijent."""
        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws") as ws,
        ):
            ws.receive_text()

    def test_websocket_wrong_token_rejected(self, app):
        """B: WebSocket sa pogrešnim tokenom je odbijen."""
        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws", headers={"Authorization": "Bearer wrong-token"}) as ws,
        ):
            ws.receive_text()

    def test_websocket_stale_token_rejected(self, app):
        """C: token neke druge (prethodne) instance je odbijen."""
        with (
            TestClient(app) as client,
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/ws", headers={"Authorization": "Bearer stale-instance-token"}
            ) as ws,
        ):
            ws.receive_text()

    def test_websocket_valid_token_accepted(self, app):
        """D: konekcija sa ispravnim trenutnim tokenom je prihvaćena."""
        with (
            TestClient(app) as client,
            client.websocket_connect(
                "/ws", headers={"Authorization": f"Bearer {_NoOpRuntimeManager.TOKEN}"}
            ),
        ):
            # Konekcija je prihvaćena — ne baca WebSocketDisconnect. Aktivno
            # zatvaramo sa naše strane (context manager exit), ne čekamo poruku.
            pass

    def test_token_not_in_url(self, app):
        """E: token se šalje kroz header, ne kroz URL query string.

        Konekcija BEZ tokena u URL-u (samo u header-u) radi — dokazuje da
        handshake ne zavisi od query stringa. Token u URL-u (bez header-a)
        NE SME proći, jer backend token nikad ne čita iz query stringa.
        """
        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws?", headers={"Authorization": f"Bearer {_NoOpRuntimeManager.TOKEN}"}
            ):
                pass

            with (
                pytest.raises(WebSocketDisconnect),
                client.websocket_connect(f"/ws?token={_NoOpRuntimeManager.TOKEN}") as ws2,
            ):
                ws2.receive_text()
