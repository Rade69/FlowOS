"""HTTP API Controllers — sistemski endpointi (/health, /version, /runtime)."""

import time

from fastapi import APIRouter, Request

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health():
    """Provera da je servis živ."""
    return {"status": "ok", "uptime": time.time() - _start_time}


@router.get("/version")
async def version():
    """Verzija servisa i API-ja."""
    return {"version": "0.1.0", "api_version": 1}


@router.get("/runtime")
async def runtime(request: Request):
    """Informacije o runtime-u servisa (PID, port, started_at)."""
    runtime_mgr = getattr(request.app.state, "runtime", None)

    pid = runtime_mgr.pid if runtime_mgr else None
    port = runtime_mgr.port if runtime_mgr else None
    data_dir = str(runtime_mgr.DESCRIPTOR_DIR.parent / "data") if runtime_mgr else None

    return {
        "pid": pid,
        "port": port,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_start_time)),
        "data_directory": data_dir,
    }
