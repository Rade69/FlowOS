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
        """Zdrav postojeći servis → vraća njegov port, bez novog Popen-a."""
        monkeypatch.setattr(composition_root, "_read_descriptor_port", lambda: 9100)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: port == 9100)

        popen_calls = []
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: popen_calls.append(a) or _FakeProc()
        )

        port = composition_root.ensure_service_running()

        assert port == 9100
        assert popen_calls == []  # nema drugog servisa

    def test_new_service_dynamic_port(self, monkeypatch):
        """Servis nije pokrenut → launch, čita NOVI port (ne 9100), vraća ga."""
        descriptor_ports = iter([None, 9105])

        def _fake_read():
            try:
                return next(descriptor_ports)
            except StopIteration:
                return 9105

        monkeypatch.setattr(composition_root, "_read_descriptor_port", _fake_read)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: port == 9105)

        popen_calls = []
        monkeypatch.setattr(
            "subprocess.Popen", lambda *a, **k: popen_calls.append(a) or _FakeProc()
        )

        port = composition_root.ensure_service_running()

        assert port == 9105
        assert len(popen_calls) == 1
        cmd = popen_calls[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "flowos.service.app"

    def test_startup_failure_raises(self, monkeypatch):
        """Servis se odmah ugasio → ServiceStartupError, bez tihog uspeha."""
        monkeypatch.setattr(composition_root, "_read_descriptor_port", lambda: None)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: False)
        monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _ExitedProc(2))

        with pytest.raises(composition_root.ServiceStartupError):
            composition_root.ensure_service_running()

    def test_startup_timeout_raises(self, monkeypatch):
        """Servis nikad ne postane zdrav → ServiceStartupError nakon bound-a."""
        monkeypatch.setattr(composition_root, "_read_descriptor_port", lambda: 9100)
        monkeypatch.setattr(composition_root, "_is_service_healthy", lambda port: False)
        monkeypatch.setattr("subprocess.Popen", lambda *a, **k: _FakeProc())
        # Ubrzaj polling: monotonic raste za 10s po pozivu, sleep no-op
        clock = iter([0.0, 10.0, 20.0, 30.0, 40.0])

        monkeypatch.setattr(time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(time, "sleep", lambda s: None)

        with pytest.raises(composition_root.ServiceStartupError):
            composition_root.ensure_service_running()


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
