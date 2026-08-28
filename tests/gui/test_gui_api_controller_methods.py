"""Testovi javnih GuiApiClient metoda koje koriste izdvojeni Controlleri."""

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QNetworkReply


def test_public_post_methods_build_canonical_payloads(qapp, monkeypatch):
    from flowos.gui.services.client import GuiApiClient

    client = GuiApiClient("http://127.0.0.1:9100")
    posts = []

    def callback(_data):
        pass

    monkeypatch.setattr(
        client, "_post", lambda path, body, signal: posts.append((path, body, signal))
    )

    client.import_plan("project-1", "# Plan\n", callback)
    client.create_tracked_session("project-1", "codex", "H:/repo", 1234)
    client.confirm_shutdown(callback)

    assert posts[0] == (
        "/projects/project-1/import-plan",
        {"markdown_text": "# Plan\n"},
        callback,
    )
    assert posts[1][:2] == (
        "/sessions",
        {
            "project_id": "project-1",
            "agent_type": "codex",
            "repo_path": "H:/repo",
            "execution_mode": "EXTERNAL_TRACKED",
            "pid": 1234,
        },
    )
    assert posts[1][2] is client.sessions_received
    assert posts[2] == ("/system/shutdown/confirm", {}, callback)


def test_prepare_shutdown_applies_auth_and_parses_dict(qapp):
    from flowos.gui.services.client import GuiApiClient

    class ImmediateSignal:
        def connect(self, callback):
            callback()

    class FakeReply:
        finished = ImmediateSignal()

        def __init__(self):
            self.deleted = False

        def error(self):
            return QNetworkReply.NetworkError.NoError

        def readAll(self):
            return QByteArray(b'{"active_sessions": 3}')

        def deleteLater(self):
            self.deleted = True

    class FakeNam:
        def __init__(self):
            self.request = None
            self.reply = FakeReply()

        def get(self, request):
            self.request = request
            return self.reply

    client = GuiApiClient("http://127.0.0.1:9100", token="instance-token")
    fake_nam = FakeNam()
    client._nam = fake_nam
    results = []

    client.prepare_shutdown(results.append)

    assert results == [{"active_sessions": 3}]
    assert fake_nam.request.url().toString() == "http://127.0.0.1:9100/system/shutdown/prepare"
    assert bytes(fake_nam.request.rawHeader("Authorization")) == b"Bearer instance-token"
    assert fake_nam.reply.deleted is True
