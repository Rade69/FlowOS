"""FLOW-1107 — GuiApiClient auth propagation testovi.

Dokazuje da GuiApiClient automatski šalje `Authorization: Bearer <token>`
na svakom zahtjevu kroz stvaran request construction put (_get/_post/_delete),
ne samo kroz helper funkciju, i da MOCK GUI (bez API klijenta) ne pokušava
backend auth uopšte.
"""

from flowos.gui.services.client import GuiApiClient


class _FakeReply:
    """Minimalan QNetworkReply-like stub sa `finished` signalom."""

    class _Signal:
        def connect(self, _fn):
            pass

    def __init__(self):
        self.finished = self._Signal()


class TestGuiApiClientAuthPropagation:
    def _capture(self, client: GuiApiClient) -> list:
        """Presreće stvaran QNetworkAccessManager.get/post/deleteResource poziv."""
        captured: list = []
        client._nam.get = lambda req: captured.append(req) or _FakeReply()
        client._nam.post = lambda req, data=None: captured.append(req) or _FakeReply()
        client._nam.deleteResource = lambda req: captured.append(req) or _FakeReply()
        return captured

    def test_get_sends_bearer_token(self, qapp):
        """A: GET zahtjev nosi Authorization: Bearer <token> na stvarnom putu."""
        client = GuiApiClient(base_url="http://127.0.0.1:9187", token="live-token-x")
        captured = self._capture(client)

        client.check_health()

        assert len(captured) == 1
        auth = captured[0].rawHeader("Authorization")
        assert bytes(auth) == b"Bearer live-token-x"

    def test_post_sends_bearer_token(self, qapp):
        """POST zahtjev (create_project) takođe nosi Authorization header."""
        client = GuiApiClient(base_url="http://127.0.0.1:9187", token="live-token-x")
        captured = self._capture(client)

        client.create_project("Test", "C:/repo")

        assert len(captured) == 1
        auth = captured[0].rawHeader("Authorization")
        assert bytes(auth) == b"Bearer live-token-x"

    def test_delete_sends_bearer_token(self, qapp):
        """DELETE zahtjev (delete_project) takođe nosi Authorization header."""
        client = GuiApiClient(base_url="http://127.0.0.1:9187", token="live-token-x")
        captured = self._capture(client)

        client.delete_project("proj-1")

        assert len(captured) == 1
        auth = captured[0].rawHeader("Authorization")
        assert bytes(auth) == b"Bearer live-token-x"

    def test_no_token_means_no_authorization_header(self, qapp):
        """Bez tokena (npr. buduća upotreba bez LIVE bootstrap-a) — header se ne šalje."""
        client = GuiApiClient(base_url="http://127.0.0.1:9187", token=None)
        captured = self._capture(client)

        client.check_health()

        assert len(captured) == 1
        auth = captured[0].rawHeader("Authorization")
        assert bytes(auth) == b""

    def test_token_never_appears_in_url(self, qapp):
        """Token se šalje kroz header, nikad ugrađen u URL zahtjeva."""
        client = GuiApiClient(base_url="http://127.0.0.1:9187", token="live-token-x")
        captured = self._capture(client)

        client.get_projects()

        assert len(captured) == 1
        url = captured[0].url().toString()
        assert "live-token-x" not in url


class TestMockModeNoAuth:
    def test_mock_gui_has_no_api_client(self, qapp):
        """MOCK GUI (bez --live) ne pravi GuiApiClient — nema backend auth pokušaja."""
        from flowos.gui.composition_root import create_gui

        gui = create_gui(use_live=False)
        assert gui._api is None
