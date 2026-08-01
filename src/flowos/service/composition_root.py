"""FlowOS Service Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve zavisnosti:
API Controllers → Backend Services → Infrastructure.

Ne koristiti dependency-injection framework. Svaka zavisnost
se prosleđuje eksplicitno kroz konstruktor.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from flowos.service.controllers.http.plan_progress import router as plan_progress_router
from flowos.service.controllers.http.project_resume import (
    router as project_resume_router,
)
from flowos.service.controllers.http.projects import router as projects_router
from flowos.service.controllers.http.system import router as system_router
from flowos.service.controllers.http.tasks import router as tasks_router
from flowos.service.services.infrastructure.persistence.engine import (
    create_session_factory,
    create_sqlite_engine,
)
from flowos.service.services.infrastructure.runtime import RuntimeManager


def create_app(runtime: RuntimeManager, engine=None) -> FastAPI:
    """Kreira i konfiguriše FastAPI aplikaciju.

    Args:
        runtime: RuntimeManager instanca (lock, descriptor, port).

    Returns:
        Konfigurisana FastAPI aplikacija spremna za uvicorn.
    """
    app = FastAPI(
        title="FlowOS",
        version="0.1.0",
        description="Lokalni lični operativni sistem za koordinaciju agentskih sesija",
        lifespan=_make_lifespan(runtime),
    )

    # Rute
    app.include_router(system_router, tags=["System"])
    app.include_router(projects_router, tags=["Projects"])
    app.include_router(tasks_router, tags=["Tasks"])
    app.include_router(plan_progress_router, tags=["Plan Progress"])
    app.include_router(project_resume_router, tags=["Project Resume"])

    # Session factory
    if engine is None:
        engine = create_sqlite_engine()
    app.state.session_factory = create_session_factory(engine)
    # Buduće rute — dodaju se kako servisi postanu dostupni
    # app.include_router(projects_router, prefix="/projects", tags=["Projects"])
    # app.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
    # app.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])

    return app


def _make_lifespan(runtime: RuntimeManager):
    """Kreira lifespan handler za FastAPI.

    Startup: inicijalizuje resurse (baza, logovi, itd.)
    Shutdown: čisti resurse (oslobađa lock, briše descriptor)
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        import logging

        from flowos.service.services.infrastructure.logging import setup_logging

        logger = setup_logging(level=logging.INFO)
        app.state.runtime = runtime

        logger.info("FlowOS servis se pokrece (pid=%d, port=%d)", runtime.pid, runtime.port)

        yield  # Servis radi...

        # Shutdown
        logger.info("FlowOS servis se gasi")
        runtime.delete_descriptor()
        runtime.release_lock()

    return lifespan
