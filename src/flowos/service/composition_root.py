"""FlowOS Service Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve zavisnosti:
API Controllers → Backend Services → Infrastructure.

Ne koristiti dependency-injection framework. Svaka zavisnost
se prosleđuje eksplicitno kroz konstruktor.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

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
    # Globalni error handler — ApiErrorResponse format
    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception):
        import uuid
        from flowos.shared.contracts.errors import ApiErrorResponse
        from flowos.shared.errors.codes import ErrorCode

        correlation_id = str(uuid.uuid4())
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content=ApiErrorResponse(
                    code=_http_to_error_code(exc.status_code),
                    message=str(exc.detail),
                    correlation_id=correlation_id,
                ).model_dump(),
            )
        return JSONResponse(
            status_code=500,
            content=ApiErrorResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="Interna greška servisa.",
                correlation_id=correlation_id,
            ).model_dump(),
        )

    return app


def _http_to_error_code(status: int) -> str:
    mapping = {400: "VALIDATION_ERROR", 404: "NOT_FOUND", 409: "CONFLICT", 422: "VALIDATION_ERROR"}
    return mapping.get(status, "INTERNAL_ERROR")


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
