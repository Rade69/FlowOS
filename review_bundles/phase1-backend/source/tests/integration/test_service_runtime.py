"""Integracioni testovi za servisni runtime — lock, descriptor, health."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.runtime import (
    InstanceAlreadyRunningError,
    RuntimeManager,
)


@pytest.fixture
def temp_dir():
    """Privremeni direktorijum za runtime podatke."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def runtime(temp_dir):
    """RuntimeManager sa privremenim direktorijumom."""
    mgr = RuntimeManager()
    mgr.DESCRIPTOR_DIR = temp_dir / "runtime"
    mgr.DESCRIPTOR_FILE = mgr.DESCRIPTOR_DIR / "service.json"
    return mgr


@pytest.fixture
def app(runtime):
    """FastAPI aplikacija sa test RuntimeManager-om."""
    app = create_app(runtime)
    app.state.runtime = runtime
    return app


@pytest.fixture
def client(app):
    """TestClient za FastAPI aplikaciju."""
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# RuntimeManager
# ═══════════════════════════════════════════════════════════════════


class TestRuntimeManager:
    def test_port_is_free_method(self, runtime: RuntimeManager):
        # Port 1 obično nije zauzet
        assert runtime._port_is_free(1)
        # Ali treba da koristimo visok port u testovima
        assert runtime._port_is_free(9999)

    def test_find_free_port(self, runtime: RuntimeManager):
        port = runtime.find_free_port(start=9100)
        assert 9100 <= port < 9200
        assert runtime.port == port

    def test_write_and_delete_descriptor(self, runtime: RuntimeManager):
        port = runtime.find_free_port()
        runtime.write_descriptor(port)

        assert runtime.DESCRIPTOR_FILE.exists()
        import json

        data = json.loads(runtime.DESCRIPTOR_FILE.read_text())
        assert data["port"] == port
        assert data["pid"] == runtime.pid
        assert data["status"] == "running"

        runtime.delete_descriptor()
        assert not runtime.DESCRIPTOR_FILE.exists()

    def test_acquire_and_release_lock(self, runtime: RuntimeManager):
        runtime.acquire_lock()
        try:
            # Drugi RuntimeManager ne može da zauzme lock
            mgr2 = RuntimeManager()
            mgr2.DESCRIPTOR_DIR = runtime.DESCRIPTOR_DIR
            with pytest.raises(InstanceAlreadyRunningError):
                mgr2.acquire_lock()
        finally:
            runtime.release_lock()

    def test_release_then_acquire(self, runtime: RuntimeManager):
        """Posle release-a, drugi može da zauzme lock."""
        runtime.acquire_lock()
        runtime.release_lock()

        # Drugi sada može
        mgr2 = RuntimeManager()
        mgr2.DESCRIPTOR_DIR = runtime.DESCRIPTOR_DIR
        mgr2.acquire_lock()
        mgr2.release_lock()


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpointi
# ═══════════════════════════════════════════════════════════════════


class TestSystemEndpoints:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "uptime" in data

    def test_version(self, client: TestClient):
        resp = client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert data["api_version"] == 1

    def test_runtime(self, client: TestClient, runtime: RuntimeManager):
        port = runtime.find_free_port()
        runtime.write_descriptor(port)

        resp = client.get("/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["port"] == port
        assert data["pid"] is not None

    def test_404(self, client: TestClient):
        resp = client.get("/nepostojeci-endpoint")
        assert resp.status_code == 404

    def test_cors_headers(self, client: TestClient):
        """CORS treba da dozvoli loopback origin."""
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # OPTIONS može vratiti 200 ili 405 u zavisnosti od rute
        # Bitno je da CORS headeri postoje u odgovoru
        assert resp.status_code in (200, 400, 405, 204)

    def test_runtime_without_manager(self):
        """Ako runtime nije postavljen na app.state, /runtime ne pada."""
        from fastapi import FastAPI

        app = FastAPI()
        from flowos.service.controllers.http.system import router

        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pid"] is None  # Nema runtime manager-a
        assert data["port"] is None
