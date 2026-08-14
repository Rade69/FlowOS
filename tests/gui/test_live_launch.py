"""Testovi za FLOW-1103 — supported LIVE launch.

Dokazuje da `ensure_service_running()` vraća potvrđeni port iz runtime
descriptor-a, ponovo koristi zdrav postojeći servis, i vidljivo prijavljuje
startup failure.
"""

import sys
import time

import pytest

from flowos.gui import composition_root


class _FakeProc:
    """Fake subprocess.Popen rezultat — nikad nije izašao."""

    def __init__(self):
        self.returncode = None

    def poll(self):
        return None


class _ExitedProc:
    """Fake subprocess.Popen rezultat — odmah izašao sa greškom."""

    def __init__(self, code=1):
        self.returncode = code

    def poll(self):
        return self.returncode


class TestLiveLaunch:
    def test_existing_healthy_service_reused(self, monkeypatch):
        """Zdrav postojeći servis → vraća njegov (port, token), bez novog Popen-a."""
        monkeypatch.setattr(
            composition_root,
            "_read_descriptor",
            lambda: composition_root.ServiceConnection(port=9100, token="token-a"),
        )
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: port == 9100)

        popen_calls = []
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: popen_calls.append(a) or _FakeProc()
        )

        result = composition_root.ensure_service_running()

        assert result.port == 9100
        assert result.token == "token-a"
        assert popen_calls == []  # nema drugog servisa

    def test_new_service_dynamic_port(self, monkeypatch):
        """Servis nije pokrenut → launch, čita NOVI (port, token) (ne 9100), vraća ih."""
        descriptors = iter([None, composition_root.ServiceConnection(port=9105, token="token-b")])

        def _fake_read():
            try:
                return next(descriptors)
            except StopIteration:
                return composition_root.ServiceConnection(port=9105, token="token-b")

        monkeypatch.setattr(composition_root, "_read_descriptor", _fake_read)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: port == 9105)

        popen_calls = []
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: popen_calls.append(a) or _FakeProc()
        )

        result = composition_root.ensure_service_running()

        assert result.port == 9105
        assert result.token == "token-b"
        assert len(popen_calls) == 1
        cmd = popen_calls[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "flowos.service.app"

    def test_startup_failure_raises(self, monkeypatch):
        """Servis se odmah ugasio → ServiceStartupError, bez tihog uspeha."""
        monkeypatch.setattr(composition_root, "_read_descriptor", lambda: None)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: False)
        monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _ExitedProc(2))

        with pytest.raises(composition_root.ServiceStartupError):
            composition_root.ensure_service_running()

    def test_startup_timeout_raises(self, monkeypatch):
        """Servis nikad ne postane zdrav → ServiceStartupError nakon bound-a."""
        monkeypatch.setattr(
            composition_root,
            "_read_descriptor",
            lambda: composition_root.ServiceConnection(port=9100, token="token-a"),
        )
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: False)
        monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _FakeProc())
        # Ubrzaj polling: monotonic raste za 10s po pozivu, sleep no-op
        clock = iter([0.0, 10.0, 20.0, 30.0, 40.0])

        monkeypatch.setattr(time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(time, "sleep", lambda s: None)

        with pytest.raises(composition_root.ServiceStartupError):
            composition_root.ensure_service_running()


class _NoOpQTimer:
    """Zamjenjuje QTimer u testu — sprječava stvaran mrežni poziv/singleShot

    da preživi test i zagadi kasnije testove na dijeljenom qapp event loop-u.
    """

    @staticmethod
    def singleShot(*_args, **_kwargs):
        pass

    def __init__(self, *args, **kwargs):
        pass

    def start(self, *args, **kwargs):
        pass

    def stop(self, *args, **kwargs):
        pass

    @property
    def timeout(self):
        class _NoOpSignal:
            def connect(self, *_args, **_kwargs):
                pass

        return _NoOpSignal()


class TestGuiCredentialPropagation:
    """FLOW-1107: create_gui() mora provući TAČAN (port, token) par u GuiApiClient."""

    def test_create_gui_live_propagates_confirmed_token(self, qapp, monkeypatch):
        """port iz instance B + token iz instance B — nikad mješavina.

        QTimer je monkeypatch-ovan na no-op — create_gui() inače zakazuje
        stvarne mrežne pozive (health check, load projects) i pokreće
        rekurentan refresh timer koji bi preživio ovaj test i pokušao
        pozvati nepostojeći server iz KASNIJIH testova na istom qapp
        event loop-u. Ovaj test dokazuje samo sinhronu wiring logiku
        (port+token propagaciju), ne timer-driven bootstrap ponašanje.
        """
        monkeypatch.setattr(
            composition_root,
            "ensure_service_running",
            lambda: composition_root.ServiceConnection(port=9187, token="confirmed-token-b"),
        )
        monkeypatch.setattr(composition_root, "QTimer", _NoOpQTimer)

        gui = composition_root.create_gui(use_live=True)

        assert gui._api is not None
        assert gui._api.base_url == "http://127.0.0.1:9187"
        assert gui._api.token == "confirmed-token-b"


class TestMockMode:
    def test_mock_mode_does_not_launch_backend(self, qapp, monkeypatch):
        """plain flowos-gui (bez --live) ne pokreće backend."""
        popen_calls = []
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: popen_calls.append(a) or _FakeProc()
        )

        gui = composition_root.create_gui(use_live=False)

        assert gui._api is None
        assert gui._controller is None
        assert popen_calls == []

    def test_mock_mode_requires_no_token(self, qapp):
        """MOCK GUI ne zahtijeva token i ne pokušava backend auth."""
        gui = composition_root.create_gui(use_live=False)

        assert gui._api is None  # nema GuiApiClient uopšte u MOCK modu
