"""HTTP API Controllers — sistemski endpointi (/health, /version, /runtime)."""

import logging
import time

from fastapi import APIRouter, Request

router = APIRouter()
_start_time = time.time()
_shutdown_requested = False

logger = logging.getLogger("flowos.system")


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


@router.get("/agents/scan")
async def scan_agents():
    """Skenira procese i pronalazi agentske procese (Claude, Codex, Crush, pi)."""
    from flowos.service.services.agent_scanner import scan_agents as do_scan

    agents = do_scan()
    return {"agents": agents, "total": len(agents)}


@router.post("/shutdown")
async def shutdown(request: Request):
    """Inicira kontrolisano gašenje servisa (odmah, bez potvrde)."""
    return await _do_shutdown(request)


@router.post("/shutdown/prepare")
async def shutdown_prepare(request: Request):
    """Vraća informacije o aktivnim sesijama pre gašenja."""
    from flowos.service.services.system_state import SystemStateService

    db = request.app.state.session_factory()
    try:
        active = SystemStateService(db).count_active_sessions()
    finally:
        db.close()

    watchers = len(getattr(request.app.state, "watchers", {}))
    can_shutdown = active == 0

    return {
        "active_sessions": active,
        "watchers": watchers,
        "can_shutdown_immediately": can_shutdown,
        "shutdown_requested": _shutdown_requested,
    }


@router.post("/shutdown/confirm")
async def shutdown_confirm(request: Request):
    """Potvrđuje gašenje — zaustavlja servis."""
    return await _do_shutdown(request)


@router.get("/shutdown/status")
async def shutdown_status():
    """Status gašenja."""
    return {
        "shutdown_requested": _shutdown_requested,
        "uptime": time.time() - _start_time,
    }


async def _do_shutdown(request: Request) -> dict:
    """Izvršava graceful shutdown."""
    global _shutdown_requested

    if _shutdown_requested:
        return {"status": "already_shutting_down"}

    _shutdown_requested = True
    logger.info("Shutdown zahtev primljen — pokrećem graceful shutdown")

    # 1. Zaustavi watcher-e
    watchers = getattr(request.app.state, "watchers", {})
    for proj_id, w in list(watchers.items()):
        try:
            w.stop()
            logger.info("Watcher zaustavljen za projekat %s", proj_id)
        except Exception:
            logger.exception("Greška pri zaustavljanju watcher-a %s", proj_id)
    watchers.clear()

    # 2. Otkaži background taskove (conflict detector, reconciliation)
    for task_name in ("conflict_task", "reconciliation_task"):
        task = getattr(request.app.state, task_name, None)
        if task:
            task.cancel()

    # 3. Zakaži gašenje uvicorn-a kroz app.state
    import asyncio

    async def _delayed_exit():
        await asyncio.sleep(1)
        import os
        import signal

        logger.info("FlowOS servis se gasi — doviđenja")
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_exit())

    return {"status": "ok", "message": "Shutdown pokrenut."}
