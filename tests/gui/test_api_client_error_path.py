"""Testovi za GuiApiClient error path — FLOW-1102.

Dokazuje da API/network greške ne izazivaju sekundarni TypeError pri
emitovanju kroz error_occurred signal, i da se Qt SignalInstance emituje
kroz `.emit()` a ne direktnim pozivom.
"""

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QNetworkReply

from flowos.gui.services.client import GuiApiClient


class _FakeReply:
    """Minimalni QNetworkReply stub za success/error put."""

    def __init__(self, error=QNetworkReply.NetworkError.NoError, error_string="", body=b""):
        self._error = error
        self._error_string = error_string
        self._body = body

    def error(self):
        return self._error

    def errorString(self):
        return self._error_string

    def readAll(self):
        return QByteArray(self._body)

    def deleteLater(self):
        pass


class TestGuiApiClientErrorPath:
    def test_error_real_signal_no_typeerror(self, qapp):
        """ERROR put sa stvarnim bound Qt signalom ne baca TypeError."""
        client = GuiApiClient(base_url="http://127.0.0.1:1")
        error_calls = []
        health_calls = []

        client.error_occurred.connect(lambda code, msg: error_calls.append((code, msg)))
        client.health_received.connect(lambda data: health_calls.append(data))

        reply = _FakeReply(
            error=QNetworkReply.NetworkError.ConnectionRefusedError,
            error_string="Connection refused",
        )
        client._handle_response(reply, client.health_received)

        # error_occurred emituje tačno jednom sa ispravnim int code-om
        assert len(error_calls) == 1
        code, msg = error_calls[0]
        assert isinstance(code, int)
        assert code == QNetworkReply.NetworkError.ConnectionRefusedError.value
        assert msg == "Connection refused"

        # request-specific signal emituje tačno jednom sa error payload-om
        assert len(health_calls) == 1
        assert health_calls[0] == {"error": "Connection refused"}

    def test_success_real_signal_no_typeerror(self, qapp):
        """SUCCESS put sa stvarnim bound Qt signalom ne baca TypeError."""
        import json

        client = GuiApiClient(base_url="http://127.0.0.1:1")
        error_calls = []
        health_calls = []

        client.error_occurred.connect(lambda code, msg: error_calls.append((code, msg)))
        client.health_received.connect(lambda data: health_calls.append(data))

        body = json.dumps({"status": "ok", "uptime": 1.5}).encode("utf-8")
        reply = _FakeReply(
            error=QNetworkReply.NetworkError.NoError,
            error_string="",
            body=body,
        )
        client._handle_response(reply, client.health_received)

        assert len(health_calls) == 1
        assert health_calls[0] == {"status": "ok", "uptime": 1.5}
        # error_occurred NE sme biti emitovan na success putu
        assert len(error_calls) == 0

    def test_plain_callable_compatibility(self, qapp):
        """Običan Python callable callback se i dalje poziva normalno."""
        client = GuiApiClient(base_url="http://127.0.0.1:1")
        got = []

        reply = _FakeReply(
            error=QNetworkReply.NetworkError.NoError,
            error_string="",
            body=b'{"ok": true}',
        )
        client._handle_response(reply, None, lambda data: got.append(data))

        assert len(got) == 1
        assert got[0] == {"ok": True}

    def test_error_no_duplicate_emission(self, qapp):
        """Jedna greška = tačno 1 error_occurred + 1 request signal emit."""
        client = GuiApiClient(base_url="http://127.0.0.1:1")
        err_count = []
        sig_count = []

        client.error_occurred.connect(lambda code, msg: err_count.append(1))
        client.health_received.connect(lambda data: sig_count.append(data))

        reply = _FakeReply(
            error=QNetworkReply.NetworkError.HostNotFoundError,
            error_string="Host not found",
        )
        client._handle_response(reply, client.health_received)

        assert len(err_count) == 1
        assert len(sig_count) == 1

    def test_no_secondary_typeerror_on_signalinstance(self, qapp):
        """SignalInstance direktno pozvan kao funkcija bi bacio TypeError — ovo ne smije."""
        client = GuiApiClient(base_url="http://127.0.0.1:1")
        got = []

        client.health_received.connect(lambda data: got.append(data))

        reply = _FakeReply(
            error=QNetworkReply.NetworkError.NoError,
            error_string="",
            body=b'{"ok": 1}',
        )
        # Ako bi _dispatch koristio callable(signal) prvi, ovo bi puklo
        client._handle_response(reply, client.health_received)

        assert got == [{"ok": 1}]
