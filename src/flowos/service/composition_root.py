"""FlowOS Service Composition Root.

Jedno mesto gde se eksplicitno konstruišu sve zavisnosti:
API Controllers → Backend Services → Infrastructure.

Ne koristiti dependency-injection framework. Svaka zavisnost
se prosleđuje eksplicitno kroz konstruktor.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from flowos.service.controllers.http.conflicts import router as conflicts_router
from flowos.service.controllers.http.plan_progress import router as plan_progress_router
from flowos.service.controllers.http.project_resume import (
    router as project_resume_router,
)
from flowos.service.controllers.http.projects import router as projects_router
from flowos.service.controllers.http.reports import router as reports_router
from flowos.service.controllers.http.sessions import (
    router as sessions_router,
)
from flowos.service.controllers.http.system import router as system_router
from flowos.service.controllers.http.tasks import router as tasks_router
from flowos.service.controllers.http.verification import (
    router as verification_router,
)
from flowos.service.controllers.websocket.events import ws_endpoint
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
    app.include_router(sessions_router, tags=["Sessions"])
    app.include_router(conflicts_router, tags=["Conflicts"])
    app.include_router(plan_progress_router, tags=["Plan Progress"])
    app.include_router(project_resume_router, tags=["Project Resume"])
    app.include_router(reports_router, tags=["Reports"])
    app.include_router(verification_router, tags=["Verification"])

    # WebSocket
    app.add_api_websocket_route("/ws", ws_endpoint)

    # Session factory
    if engine is None:
        engine = create_sqlite_engine()
    app.state.session_factory = create_session_factory(engine)

    # Background task fabrika za session completion
    def _make_complete_session():
        from flowos.service.services.sessions.completion import (
            SessionCompletionService,
        )

        def _complete(
            session_id: str,
            exit_code: int | None = None,
            result_commit_sha: str | None = None,
        ) -> None:
            bg_engine = create_sqlite_engine()
            bg_factory = create_session_factory(bg_engine)
            bg_db = bg_factory()
            try:
                completion = SessionCompletionService(bg_db)
                completion.complete_session(
                    session_id=session_id,
                    exit_code=exit_code,
                    result_commit_sha=result_commit_sha,
                )
            except Exception:
                import logging

                logging.getLogger("flowos.session_completion").exception(
                    "Session completion failed for %s", session_id
                )
            finally:
                bg_db.close()

        return _complete

    app.state.complete_session = _make_complete_session()

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

    Startup: inicijalizuje resurse (baza, logovi, watcher, konflikt detektor)
    Shutdown: čisti resurse (zaustavlja watcher, otkazuje taskove, oslobađa lock)
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        import asyncio
        import contextlib
        import logging
        import uuid

        from flowos.service.services.activity.service import ActivityService
        from flowos.service.services.attribution.service import ActiveSession
        from flowos.service.services.infrastructure.logging import setup_logging
        from flowos.service.services.infrastructure.persistence.engine import (
            create_session_factory,
            create_sqlite_engine,
        )
        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
        )
        from flowos.service.services.infrastructure.watcher import WatcherPipeline
        from flowos.shared.enums.session import SessionStatus

        logger = setup_logging(level=logging.INFO)
        app.state.runtime = runtime

        # Watcher kolekcija — jedan watcher po projektu
        app.state.watchers: dict[str, WatcherPipeline] = {}  # type: ignore[misc]  # starlette State je netipiziran

        # Watcher callback — povezuje watcher → ActivityService → baza
        def _make_watcher_callback(project_id: str, repo_path: str):
            """Fabrika callback-a za određeni projekat.

            Svaki watcher događaj se trajno beleži u FileActivity tabelu
            sa atribucijom aktivnim sesijama.
            """
            db_engine = create_sqlite_engine()
            db_factory = create_session_factory(db_engine)

            def _callback(event):
                correlation_id = str(uuid.uuid4())
                db = db_factory()
                try:
                    # Učitaj aktivne sesije za ovaj projekat
                    active_sessions_raw = (
                        db.query(AgentSession)
                        .filter(
                            AgentSession.project_id == project_id,
                            AgentSession.status.in_(
                                (SessionStatus.ACTIVE.value, SessionStatus.IDLE.value)
                            ),
                        )
                        .all()
                    )

                    active = [
                        ActiveSession(
                            session_id=s.id,
                            worktree_path=s.worktree_path,
                            repo_path=s.repo_path,
                        )
                        for s in active_sessions_raw
                    ]

                    activity_svc = ActivityService(db)

                    # Registruj conflict callback za WRITE_WRITE i LATE_OVERLAP
                    if len(active) >= 2:

                        def _make_conflict_cb(project_id, active_sessions):
                            def _cb(activity):
                                from flowos.service.services.conflicts.service import (
                                    ConflictDetectionService,
                                )

                                conflict_svc = ConflictDetectionService(db)
                                conflict_svc.on_file_activity(activity, active_sessions)
                                db.commit()

                            return _cb

                        activity_svc.register_conflict_callback(
                            _make_conflict_cb(project_id, active)
                        )

                    _activity = activity_svc.record_file_event(
                        file_path=event.path,
                        event_type=event.event_type,
                        project_id=project_id,
                        repo_path=repo_path,
                        active_sessions=active,
                        source="WATCHER",
                        metadata={"correlation_id": correlation_id},
                    )
                    db.commit()

                except Exception:
                    db.rollback()
                    logger.exception(
                        "Watcher callback greška [%s]: %s %s",
                        correlation_id,
                        event.event_type,
                        event.path,
                    )
                finally:
                    db.close()

            return _callback

        # Učitaj aktivne projekte i pokreni watcher-e
        engine = create_sqlite_engine()
        init_factory = create_session_factory(engine)
        init_db = init_factory()
        try:
            projects = init_db.query(Project).all()
            for proj in projects:
                try:
                    cb = _make_watcher_callback(proj.id, proj.repo_path)
                    w = WatcherPipeline(callback=cb)
                    w.start(proj.repo_path)
                    app.state.watchers[proj.id] = w
                    logger.info("Watcher pokrenut za projekat %s: %s", proj.id, proj.repo_path)
                except FileNotFoundError:
                    logger.warning(
                        "Repo putanja ne postoji za projekat %s: %s — preskačem",
                        proj.id,
                        proj.repo_path,
                    )
                except Exception:
                    logger.exception("Greška pri pokretanju watcher-a za projekat %s", proj.id)
        except Exception:
            logger.exception("Greška pri učitavanju projekata za watcher-e")
        finally:
            init_db.close()

        # Periodični konflikt detektor — proverava svakih 60s
        async def _conflict_detector():
            """Periodično proverava konflikte među aktivnim sesijama."""
            await asyncio.sleep(10)  # sačekaj da se servis stabilizuje
            while True:
                try:
                    _run_conflict_detection(app)
                except Exception:
                    logger.exception("Conflict detection failed")
                await asyncio.sleep(60)

        conflict_task = asyncio.create_task(_conflict_detector())
        app.state.conflict_task = conflict_task

        logger.info("FlowOS servis se pokrece (pid=%d, port=%d)", runtime.pid, runtime.port)

        yield  # Servis radi...

        # Shutdown
        logger.info("FlowOS servis se gasi")
        conflict_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await conflict_task
        # Zaustavi sve watcher-e
        for proj_id, w in app.state.watchers.items():
            try:
                w.stop()
                logger.info("Watcher zaustavljen za projekat %s", proj_id)
            except Exception:
                logger.exception("Greška pri zaustavljanju watcher-a za projekat %s", proj_id)
        app.state.watchers.clear()
        runtime.delete_descriptor()
        runtime.release_lock()

    return lifespan


def _run_conflict_detection(app: FastAPI) -> None:
    """Izvršava jedan ciklus detekcije konflikata.

    Proverava:
    - STALE_SESSION — sesije bez aktivnosti > 30 min
    - BRANCH_CHANGE — branch promenjen ispod aktivne sesije
    """
    from flowos.service.services.conflicts.service import ConflictDetectionService
    from flowos.service.services.infrastructure.git_poller import GitStateReader
    from flowos.service.services.infrastructure.persistence.engine import (
        create_session_factory,
        create_sqlite_engine,
    )
    from flowos.service.services.infrastructure.persistence.models import AgentSession
    from flowos.shared.enums.session import SessionStatus

    engine = create_sqlite_engine()
    factory = create_session_factory(engine)
    db = factory()
    try:
        # Pronađi sve aktivne sesije
        active = (
            db.query(AgentSession)
            .filter(AgentSession.status.in_((SessionStatus.ACTIVE.value, SessionStatus.IDLE.value)))
            .all()
        )

        if not active:
            return

        svc = ConflictDetectionService(db)

        for session in active:
            if not session.project_id:
                continue

            # STALE_SESSION — sesija bez aktivnosti > 30 min
            if session.last_activity_at:
                svc.detect_stale_session(session.project_id, session)

            # BRANCH_CHANGE — proveri da li se branch promenio
            if session.repo_path and session.branch_name:
                try:
                    reader = GitStateReader(session.repo_path)
                    git_state = reader.read_state()
                    if git_state.branch and git_state.branch != session.branch_name:
                        svc.detect_branch_change(
                            session.project_id,
                            session,
                            session.branch_name,
                            git_state.branch,
                        )
                except Exception:
                    import logging

                    logging.getLogger("flowos.conflict").warning(
                        "BRANCH_CHANGE provera nije uspela za sesiju %s", session.id
                    )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
